import { NavLink, Outlet } from "react-router-dom";
import { FileText, LayoutDashboard, Settings, Play, BookOpen, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { triggerRun } from "@/lib/api";
import { useState } from "react";

function NavItem({
  to,
  children,
  onClick,
}: {
  to: string;
  children: React.ReactNode;
  onClick?: () => void;
}) {
  return (
    <NavLink
      to={to}
      end
      onClick={onClick}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors",
          isActive
            ? "bg-white/10 text-white"
            : "text-white/60 hover:text-white hover:bg-white/5",
        )
      }
    >
      {children}
    </NavLink>
  );
}

export function Layout() {
  const [running, setRunning] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const handleTrigger = async () => {
    setRunning(true);
    setMenuOpen(false);
    try {
      await triggerRun();
    } finally {
      setTimeout(() => setRunning(false), 3000);
    }
  };

  const closeMenu = () => setMenuOpen(false);

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 bg-[#1d1d1f] shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            {/* Logo */}
            <NavLink
              to="/"
              className="text-white font-semibold text-lg tracking-tight flex items-center gap-2"
              onClick={closeMenu}
            >
              <FileText className="h-5 w-5 text-primary" />
              DocFlow
            </NavLink>

            {/* Desktop Nav */}
            <nav className="hidden sm:flex items-center gap-1">
              <NavItem to="/">
                <LayoutDashboard className="h-4 w-4" />
                Dashboard
              </NavItem>
              <NavItem to="/documents">
                <FileText className="h-4 w-4" />
                Dokumente
              </NavItem>
              <NavItem to="/settings">
                <Settings className="h-4 w-4" />
                Einstellungen
              </NavItem>
              <a
                href="/docs/"
                className="flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium text-white/60 hover:text-white hover:bg-white/5 transition-colors"
              >
                <BookOpen className="h-4 w-4" />
                Doku
              </a>
            </nav>

            {/* Desktop Run Button + Mobile Hamburger */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleTrigger}
                disabled={running}
                className={cn(
                  "hidden sm:flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium transition-all",
                  running
                    ? "bg-success/20 text-success cursor-wait"
                    : "bg-primary text-primary-foreground hover:bg-primary/90 active:scale-95",
                )}
              >
                <Play className="h-3.5 w-3.5" />
                {running ? "Gestartet..." : "Jetzt ausführen"}
              </button>

              {/* Hamburger – mobile only */}
              <button
                className="sm:hidden p-2 text-white/70 hover:text-white transition-colors"
                onClick={() => setMenuOpen((o) => !o)}
                aria-label="Menü öffnen"
              >
                {menuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Drawer */}
        {menuOpen && (
          <div className="sm:hidden bg-[#2c2c2e] border-t border-white/10 px-4 py-3 flex flex-col gap-1">
            <NavItem to="/" onClick={closeMenu}>
              <LayoutDashboard className="h-4 w-4" />
              Dashboard
            </NavItem>
            <NavItem to="/documents" onClick={closeMenu}>
              <FileText className="h-4 w-4" />
              Dokumente
            </NavItem>
            <NavItem to="/settings" onClick={closeMenu}>
              <Settings className="h-4 w-4" />
              Einstellungen
            </NavItem>
            <a
              href="/docs/"
              onClick={closeMenu}
              className="flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium text-white/60 hover:text-white hover:bg-white/5 transition-colors"
            >
              <BookOpen className="h-4 w-4" />
              Doku
            </a>
            <div className="pt-2 border-t border-white/10 mt-1">
              <button
                onClick={handleTrigger}
                disabled={running}
                className={cn(
                  "w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all",
                  running
                    ? "bg-success/20 text-success cursor-wait"
                    : "bg-primary text-primary-foreground hover:bg-primary/90",
                )}
              >
                <Play className="h-4 w-4" />
                {running ? "Gestartet..." : "Jetzt ausführen"}
              </button>
            </div>
          </div>
        )}
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
}
