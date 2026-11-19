/** @type {import('next').NextConfig} */
export default {
  poweredByHeader: false,
  reactStrictMode: true,
  async redirects() {
    // Links written by the Notification service (it knows nothing about the UI layout) map onto the screens here.
    return [
      { source: "/settings/fees", destination: "/sme/fees", permanent: false },
      { source: "/sme/applications/:id", destination: "/sme/loans/:id", permanent: false },
      { source: "/sme/access-requests", destination: "/sme/privacy", permanent: false },
      { source: "/lender/applications/:id", destination: "/lender/apps/:id", permanent: false },
    ];
  },
  async headers() {
    return [{ source: "/:path*", headers: [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "same-origin" },
    ] }];
  },
};
