import { useEffect, useState, useMemo } from "react";
import { useLocation, useParams, matchPath } from "react-router-dom";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { getProject } from "@/api/projects";

interface AppShellProps {
  children: React.ReactNode;
}

interface BreadcrumbItem {
  label: string;
  href?: string;
}

function useCurrentProject() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<{ id: string; name: string } | null>(null);

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (!id) {
      setProject(null);
      return;
    }
    let cancelled = false;
    getProject(id)
      .then((p) => {
        if (!cancelled) setProject({ id, name: p.name || id });
      })
      .catch(() => {
        if (!cancelled) setProject({ id, name: id });
      });
    return () => {
      cancelled = true;
    };
  }, [id]);
  /* eslint-enable react-hooks/set-state-in-effect */

  return project;
}

function useBreadcrumbs(projectName: string): BreadcrumbItem[] | null {
  const location = useLocation();

  return useMemo(() => {
    // 当前仅写作工作台页面启用新 topbar；其他页面保持原有自包含标题区
    const path = location.pathname;
    if (matchPath("/projects/:id/write", path)) {
      return [
        { label: "项目列表", href: "/projects" },
        { label: projectName || "项目详情" },
        { label: "写作工作台" },
      ];
    }

    if (matchPath("/projects/:id/dashboard", path)) {
      return [
        { label: "项目列表", href: "/projects" },
        { label: projectName || "项目详情" },
        { label: "项目仪表盘" },
      ];
    }

    if (path === "/projects") return [{ label: "项目列表" }];
    if (path.startsWith("/create")) return [{ label: "创建项目" }];
    if (path === "/settings/llm") return [{ label: "系统设置" }, { label: "LLM 配置" }];
    if (path === "/") return [{ label: "仪表盘" }];

    return null;
  }, [location.pathname, projectName]);
}

export function AppShell({ children }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const currentProject = useCurrentProject();
  const breadcrumbs = useBreadcrumbs(currentProject?.name || "");
  const showTopbar = breadcrumbs != null;

  return (
    <div className="min-h-[100dvh] bg-background">
      <Sidebar
        currentProject={currentProject || undefined}
        open={sidebarOpen}
        onOpenChange={setSidebarOpen}
      />
      <main className="md:pl-64">
        {showTopbar && (
          <Topbar
            title="Novel-OS"
            breadcrumbs={breadcrumbs || undefined}
            onMenuClick={() => setSidebarOpen(true)}
          />
        )}
        <div
          className={
            showTopbar
              ? "h-[calc(100dvh-3.5rem)] overflow-y-auto"
              : "h-[100dvh] overflow-y-auto"
          }
        >
          {children}
        </div>
      </main>
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm md:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}
    </div>
  );
}
