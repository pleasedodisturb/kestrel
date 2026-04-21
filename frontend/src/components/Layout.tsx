import { Link, useLocation, Outlet } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Kanban, BarChart3, Bell, Settings, Sparkles, BookOpen, Compass, Mic, Activity, Users, HelpCircle } from "lucide-react";
import { FeedbackButton } from "@/components/FeedbackButton";
import { TourProvider } from "@/components/TourProvider";

const navItems = [
  { to: "/", label: "Pipeline", icon: Kanban },
  { to: "/discovery", label: "Discovery", icon: Compass },
  { to: "/follow-ups", label: "Follow-Ups", icon: Bell },
  { to: "/contacts", label: "Contacts", icon: Users },
  { to: "/skills", label: "Skills", icon: Sparkles },
  { to: "/learning", label: "Learning", icon: BookOpen },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/voice", label: "Voice", icon: Mic },
  { to: "/ai-health", label: "AI Health", icon: Activity },
  { to: "/settings", label: "Settings", icon: Settings },
  { to: "/help", label: "Help", icon: HelpCircle },
];

export function Layout() {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="border-b bg-white shadow-sm">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold text-gray-900">Career OS</span>
            </div>
            <div className="flex items-center gap-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive =
                  item.to === "/"
                    ? location.pathname === "/" ||
                      location.pathname.startsWith("/applications")
                    : location.pathname.startsWith(item.to);
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={cn(
                      "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-gray-100 text-gray-900"
                        : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      </nav>
      <TourProvider>
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
        <FeedbackButton />
      </TourProvider>
    </div>
  );
}
