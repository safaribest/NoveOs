import { useState } from "react";
import { Bell, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useNotificationStore } from "@/stores/notification-store";
import { cn } from "@/lib/utils";

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const { notifications, unreadCount, markAllAsRead, clearAll, removeNotification } = useNotificationStore();

  const handleOpen = () => {
    setOpen(true);
    markAllAsRead();
  };

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        onClick={handleOpen}
        className="relative h-9 w-9 text-muted-foreground transition-colors hover:text-foreground"
        aria-label="通知"
      >
        <Bell className="size-4" />
        {unreadCount > 0 && (
          <span className="absolute right-1.5 top-1.5 flex size-2 items-center justify-center">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-75" />
            <span className="relative inline-flex size-1.5 rounded-full bg-primary" />
          </span>
        )}
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-sm border-glass-border bg-glass-bg p-0 shadow-2xl backdrop-blur-glass">
          <DialogHeader className="flex flex-row items-center justify-between border-b border-border/60 px-4 py-3">
            <DialogTitle className="text-base">通知中心</DialogTitle>
            <div className="flex items-center gap-1">
              {notifications.length > 0 && (
                <Button variant="ghost" size="icon" className="size-7" onClick={clearAll}>
                  <Trash2 className="size-3.5 text-muted-foreground" />
                </Button>
              )}
            </div>
          </DialogHeader>
          <div className="max-h-[60vh] overflow-y-auto p-2">
            {notifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 text-center text-sm text-muted-foreground">
                <Bell className="mb-2 size-8 opacity-30" />
                暂无通知
              </div>
            ) : (
              <div className="space-y-1">
                {notifications.map((n) => (
                  <div
                    key={n.id}
                    className={cn(
                      "group relative rounded-lg border p-3 transition-colors",
                      n.read
                        ? "border-border/40 bg-background/40"
                        : "border-primary/20 bg-primary/5"
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium">{n.title}</p>
                        {n.message && <p className="mt-0.5 text-xs text-muted-foreground">{n.message}</p>}
                        <p className="mt-1 text-[10px] text-muted-foreground/70">
                          {new Date(n.createdAt).toLocaleString("zh-CN")}
                        </p>
                      </div>
                      <button
                        onClick={() => removeNotification(n.id)}
                        className="rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-foreground/5 group-hover:opacity-100"
                      >
                        <X className="size-3" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
