import Link from "next/link";
import { useTranslations } from "next-intl";

export default function Home() {
  const t = useTranslations("home");

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F4F6F8]">
      <main className="flex flex-col items-center gap-8 text-center">
        <div className="text-5xl">🤖</div>
        <h1 className="text-3xl font-bold text-[#0C1E35]">
          {t("heading")}
        </h1>
        <p className="max-w-md text-[#64748B]">
          {t("subheading")}
        </p>
        <Link
          href="/collections-assistant"
          className="rounded-lg px-8 py-3 text-sm font-bold text-white transition-colors"
          style={{ background: "linear-gradient(135deg, #0D9488, #134E4A)" }}
        >
          {t("launchButton")}
        </Link>
      </main>
    </div>
  );
}
