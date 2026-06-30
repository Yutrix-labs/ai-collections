import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

// auth-bff base URL. /auth/* is proxied here so the browser stays same-origin
// (first-party session cookie, CSRF works). Override with BFF_URL.
const BFF = process.env.BFF_URL || "http://localhost:8080";

const nextConfig: NextConfig = {
    reactStrictMode: false,
    output: "standalone",
    async rewrites() {
        return [{ source: "/auth/:path*", destination: `${BFF}/auth/:path*` }];
    },
};

export default withNextIntl(nextConfig);
