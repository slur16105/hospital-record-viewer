# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

병원 진료기록 조회 시스템. 환자/의사/관리자 3개 역할의 웹앱이며, Flutter는 이 웹을 감싸는 WebView 쉘이다.

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
  → frontend/proxy.ts        (미들웨어: 세션 확인 + 역할 기반 라우팅/가드)
  → frontend/app/api/**/route.ts  (BFF: 쿠키에서 토큰 추출 → FastAPI로 Bearer 전달)
  → backend FastAPI          (JWKS로 JWT 검증 → Supabase 호출)
  → Supabase (PostgREST/Auth)
```

- **프론트엔드는 DB에 직접 가지 않는다.** `app/api/**/route.ts` 핸들러가 BFF 역할로 FastAPI(`process.env.FASTAPI_URL`)에 `Authorization: Bearer <token>`을 붙여 프록시한다. 새 데이터 기능은 거의 항상 `frontend/app/api/...` 라우트 핸들러 + `backend/routers/...` 엔드포인트를 **쌍으로** 추가하는 패턴이다.
- **토큰 추출:** `frontend/lib/supabase/token.ts`의 `getAccessToken()`이 `sb-<ref>-auth-token` 쿠키를 **직접 파싱**한다 (`getUser()` 네트워크 왕복 없음, 청크 쿠키·`base64-` 접두사 처리 포함). 유효성 검증은 백엔드에 위임.
- **역할 가드:** `frontend/proxy.ts`가 `/admin` `/doctor` `/patient` 보호 경로, 역할 불일치 리다이렉트, `/register` 차단(관리자만 계정 생성), 의사 `must_change_password` 강제 `/change-password`를 모두 처리한다.
- **백엔드 DB 접근:** `backend/core/database.py`에 3종 클라이언트 — `get_supabase()`(anon), `get_supabase_admin()`(service_role, 라우터 대부분이 이걸 사용), `get_supabase_for_user(token)`(RLS 적용). 엔드포인트는 `Depends(get_current_user)`로 JWT를 검증한 뒤 `current_user["sub"]`로 사용자를 식별한다.

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

`admin@hospital.test / Admin123!` · `doctor01@hospital.test / Doctor123!` · `patient01@hospital.test / Patient123!`

---

## ⚠️ 이 프로젝트의 함정 (놓치기 쉬움 — 반드시 숙지)

1. **JWT는 ES256(비대칭/JWKS)이다, HS256 아님.** Supabase가 비대칭 서명키로 마이그레이션됨. `backend/core/auth.py`는 JWKS 공개키(`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`)로 검증하고 HS256은 레거시 폴백으로만 둔다. "유효 토큰이 전부 401" 증상이면 이 검증 경로부터 의심할 것. (회귀 테스트: `tests/test_auth.py`)

2. **PostgREST 임베드(`select("...departments!inner(name)")` 등)는 FK 관계가 있어야 동작한다.** `patients`/`doctors` ↔ `user_profiles` FK는 `supabase/migrations/00009_profile_relationships.sql`에서 정의됨. 목록 API가 500 나면 이 FK/임베드부터 확인. `!inner` JOIN은 현재 RLS가 "all authenticated"라 동작하지만 RLS 강화 시 결과 누락 위험.

3. **Next.js 16 — 알던 Next가 아니다.** `frontend/AGENTS.md` 경고대로 API·관례·파일 구조가 다를 수 있다. 미들웨어 파일이 `middleware.ts`가 아니라 **`proxy.ts`**다. 코드 작성 전 `node_modules/next/dist/docs/`의 해당 가이드를 확인할 것.

4. **이연된 보안 작업이 있다.** `_bmad-output/implementation-artifacts/deferred-work.md`에 JWT `iss` 클레임 검증, Supabase 예외 처리, `X-Forwarded-For` IP 처리, 클라이언트 싱글톤화 등 7건이 미처리 상태로 기록되어 있음. 운영 하드닝 작업 시 여기부터 볼 것.

## BMad 산출물

기획/구현 산출물은 `_bmad-output/`에 있다 — `planning-artifacts/`(PRD, 아키텍처 스파인, ERD, 에픽), `implementation-artifacts/`(스토리별 스펙, `sprint-status.yaml`, `deferred-work.md`, 테스트 요약). 진행 상황은 `sprint-status.yaml`이 기준이다 (현재 Epic 1~5 전부 `done`).
