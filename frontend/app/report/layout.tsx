"use client";

import { useParams } from "next/navigation";
import AppNav from "@/components/nav/AppNav";
import Protected from "@/components/auth/Protected";
import { useSpecLabel } from "@/lib/useSpecLabel";

export default function ReportLayout({ children }: { children: React.ReactNode }) {
  const { spec_id } = useParams<{ spec_id: string }>();
  const specLabel = useSpecLabel(spec_id);

  return (
    <div className="flex min-h-screen flex-col bg-bg text-text print:bg-white print:text-black">
      <AppNav
        className="print:hidden"
        crumbs={[
          { label: "Dashboard", href: "/dashboard" },
          { label: specLabel, href: `/calls/${spec_id}` },
          { label: "Report" },
        ]}
      />
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-6 py-8 sm:px-10 lg:py-12 print:max-w-none print:px-0">
        <Protected>{children}</Protected>
      </main>
    </div>
  );
}
