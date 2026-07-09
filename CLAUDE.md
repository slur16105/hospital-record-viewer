# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

병원 진료기록 조회 시스템. **동적 RBAC(SaaS Starter Kit) 코어** 위의 병원 앱 모듈 구조다 — 역할·권한·입력필드는 관리자가 화면에서 정의하는 데이터이고(시드: 관리자/의사/환자/원무과), API 접근 판정은 권한 코드로만 한다. Flutter는 이 웹을 감싸는 WebView 쉘이다.

## 구성 요소 (배포 단위)

| 디렉토리 | 스택 | 배포 | 역할 |
|---------|------|------|------|
| `frontend/` | Next.js 16 (App Router, React 19, TS) | Railway | UI + BFF 프록시 |
| `backend/` | FastAPI (Python) | Railway | 진짜 API. Supabase 접근 |
| `supabase/` | Postgres + Auth (PostgREST) | Supabase | DB · 인증 · RLS |
| `flutter-app/` | Flutter + `webview_flutter` | iOS/Android | 배포된 웹을 띄우는 얇은 WebView 쉘 (앱 로직 거의 없음) |
| `scripts/seed.py` | Python | — | 데모 시드 데이터 |

## 요청 흐름 (핵심 아키텍처)

```
브라우저
  → frontend/proxy.ts        (미들웨어: **인증만** — 세션 유무·must_change_password. 역할/권한 판정 없음)
  → frontend/app/api/**/route.ts  (BFF: 쿠키에서 토큰 추출 → FastAPI로 Bearer 전달, 판정 없음)
  → backend FastAPI          (JWKS로 JWT 검증 → require_permission("<code>") 인가 → Supabase 호출)
  → Supabase (PostgREST/Auth)
```

- **프론트엔드는 DB에 직접 가지 않는다.** `app/api/**/route.ts` 핸들러가 BFF 역할로 FastAPI(`process.env.FASTAPI_URL`)에 `Authorization: Bearer <token>`을 붙여 프록시한다. 새 데이터 기능은 거의 항상 `frontend/app/api/...` 라우트 핸들러 + `backend/routers/...` 엔드포인트를 **쌍으로** 추가하는 패턴이다.
- **토큰 추출:** `frontend/lib/supabase/token.ts`의 `getAccessToken()`이 `sb-<ref>-auth-token` 쿠키를 **직접 파싱**한다 (`getUser()` 네트워크 왕복 없음, 청크 쿠키·`base64-` 접두사 처리 포함). 유효성 검증은 백엔드에 위임.
- **인가(권한) 판정은 백엔드가 유일한 판정자다.** 모든 보호 엔드포인트는 `Depends(require_permission(P.XXX))`(`backend/core/authz.py`) 선언 — 역할명 문자열 분기 금지. 권한 코드 단일 원본은 `backend/core/permissions.py`(시드 00011과 동기화, 단위 테스트로 고정). 프론트 메뉴/화면 노출은 `GET /api/me`의 permissions 기반(`frontend/lib/menu.ts`, `lib/permissions.ts`) — UX일 뿐 보안 경계 아님. URL은 기능 기준(`/records` `/patients` `/users` `/roles` `/departments` `/access-logs`), 구 역할 경로는 리다이렉트만 남음. 셀프 가입 없음(계정은 `users:create` 보유자가 발급 — 초대 링크/임시비번).
- **동적 필드:** 역할별 입력필드 정의는 `role_fields`(폼 빌더), 값은 `profile_field_values`(typed EAV). 검증·저장은 `backend/core/field_values.py` 단일 경유, 프론트 렌더는 `components/DynamicForm` 단일 렌더러.
- **백엔드 DB 접근:** `backend/core/database.py`에 3종 클라이언트 — `get_supabase()`(anon), `get_supabase_admin()`(service_role, 라우터 대부분이 이걸 사용), `get_supabase_for_user(token)`(RLS 적용). 엔드포인트는 `Depends(require_permission(...))`(내부에서 JWT 검증 포함)로 인가하고 `current_user["sub"]`로 사용자를 식별한다.

## 자주 쓰는 명령어

### 백엔드 (`cd backend`)
```bash
pip install -r requirements.txt          # 운영 의존성
pip install -r requirements-dev.txt      # + pytest (테스트용)
uvicorn main:app --reload                # 로컬 개발 서버
pytest                                   # 전체 테스트
pytest tests/test_auth.py                # 파일 단위
pytest tests/test_auth.py::test_valid_token_returns_200   # 단일 테스트
```
> ⚠️ `backend/tests/`는 **통합 테스트**다 — 단위 테스트가 아니라 **배포된(또는 `BACKEND_URL`로 지정한) 백엔드 + 실제 Supabase Auth**를 대상으로 돌고, 시드 계정으로 토큰을 발급받아 검증한다. 로컬을 대상으로 하려면 `BACKEND_URL=http://localhost:8000 pytest`. Supabase 자격은 `backend/.env`에서 자동 로드된다.

### 프론트엔드 (`cd frontend`)
```bash
npm install
npm run dev      # next dev (localhost:3000)
npm run build
npm run lint     # eslint
npm run start    # next start -p ${PORT:-3000}
```

### 시드 / DB
```bash
python scripts/seed.py            # backend/.env 의 SERVICE_ROLE 키 사용
# 마이그레이션: supabase/migrations/0000N_*.sql (순번대로 Supabase에 적용)
```

## 환경 변수

- **`backend/.env`** (`.env.example` 참고): `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `CORS_ORIGINS`(쉼표 구분, 미설정 시 `*`)
- **프론트엔드:** `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `FASTAPI_URL`(백엔드 주소)

## 시드 계정 (`scripts/seed.py` 기준)

`admin@hospital.test / Admin123!` · `doctor01@hospital.test / Doctor123!` · `patient01@hospital.test / Patient123!` · `staff01@hospital.test / Staff123!`(원무과, seed 실행 시)

---

## ⚠️ 이 프로젝트의 함정 (놓치기 쉬움 — 반드시 숙지)

1. **JWT는 ES256(비대칭/JWKS)이다, HS256 아님.** Supabase가 비대칭 서명키로 마이그레이션됨. `backend/core/auth.py`는 JWKS 공개키(`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`)로 검증하고 HS256은 레거시 폴백으로만 둔다. "유효 토큰이 전부 401" 증상이면 이 검증 경로부터 의심할 것. (회귀 테스트: `tests/test_auth.py`)

2. **레거시 스키마는 완전히 제거됐다 (00013 적용 완료, 2026-07-09).** `doctors`/`patients` 테이블·`user_profiles.role` enum은 더 이상 존재하지 않는다 — 역할은 `user_roles`, 역할별 데이터는 `role_fields`+`profile_field_values`, 진료기록 연결은 `patient_user_id`/`doctor_user_id`. **환자/의사 식별자는 전부 auth user_id다** (API 응답의 id 포함). 구 RLS 정책·헬퍼 함수(is_admin 등)도 제거됨 — RLS는 ENABLE 상태로 anon 차단만 하고, 인가는 백엔드가 전담.

3. **Next.js 16 — 알던 Next가 아니다.** `frontend/AGENTS.md` 경고대로 API·관례·파일 구조가 다를 수 있다. 미들웨어 파일이 `middleware.ts`가 아니라 **`proxy.ts`**다. 코드 작성 전 `node_modules/next/dist/docs/`의 해당 가이드를 확인할 것.

4. **이연 작업 현황은 `_bmad-output/implementation-artifacts/deferred-work.md` 참고.** 2026-07-09 RBAC v2 재편으로 #5(!inner JOIN 취약성)는 해소(권한 판정 백엔드 일원화). 남은 게이트: 00013 레거시 제거(함정 #2 참조). v2 재편 전체 맥락은 `_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-09.md`.

## BMad 산출물

기획/구현 산출물은 `_bmad-output/`에 있다 — `planning-artifacts/`(PRD, 아키텍처 스파인, ERD, 에픽), `implementation-artifacts/`(스토리별 스펙, `sprint-status.yaml`, `deferred-work.md`, 테스트 요약). 진행 상황은 `sprint-status.yaml`이 기준이다 (Epic 1~10 전부 `done` — Epic 6~10은 2026-07-09 RBAC v2 재편).
