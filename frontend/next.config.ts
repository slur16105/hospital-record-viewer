import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 구 역할 경로 → 기능 경로 리다이렉트 (Story 9.3, AD-7).
  // 순서 중요: 구체적인 패턴(예: /new)이 먼저 매칭돼야 한다.
  async redirects() {
    return [
      // /doctor/*
      {
        source: '/doctor/patients/:id/records/new',
        destination: '/patients/:id/records/new',
        permanent: false,
      },
      {
        source: '/doctor/patients/:id/records/:recordId',
        destination: '/records/:recordId?patient=:id',
        permanent: false,
      },
      {
        source: '/doctor/patients/:id/records',
        destination: '/patients/:id/records',
        permanent: false,
      },
      { source: '/doctor/search', destination: '/patients?tab=search', permanent: false },
      { source: '/doctor/:path*', destination: '/patients', permanent: false },
      { source: '/doctor', destination: '/patients', permanent: false },
      // /patient/*
      { source: '/patient/records/:recordId', destination: '/records/:recordId', permanent: false },
      { source: '/patient/:path*', destination: '/records', permanent: false },
      { source: '/patient', destination: '/records', permanent: false },
      // /admin/*
      { source: '/admin/departments', destination: '/departments', permanent: false },
      { source: '/admin/rooms', destination: '/departments?tab=rooms', permanent: false },
      { source: '/admin/access-logs', destination: '/access-logs', permanent: false },
      { source: '/admin/doctors', destination: '/users', permanent: false },
      { source: '/admin/patients', destination: '/users', permanent: false },
      { source: '/admin/:path*', destination: '/users', permanent: false },
      { source: '/admin', destination: '/users', permanent: false },
      // /register 제거 (관리자만 계정 생성 — 통합 /users/new)
      { source: '/register', destination: '/login', permanent: false },
    ];
  },
};

export default nextConfig;
