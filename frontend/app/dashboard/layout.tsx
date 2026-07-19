import AppNav from "@/components/nav/AppNav";
import Protected from "@/components/auth/Protected";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-bg text-text">
      <AppNav crumbs={[{ label: "Dashboard" }]} />
      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-6 py-10 sm:px-10 lg:py-14">
        <Protected>{children}</Protected>
      </main>
    </div>
  );
}
