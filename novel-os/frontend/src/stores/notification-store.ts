import { create } from "zustand";

export interface Notification {
  id: string;
  title: string;
  message?: string;
  type?: "info" | "success" | "warning" | "error";
  read: boolean;
  createdAt: number;
}

interface NotificationStore {
  notifications: Notification[];
  unreadCount: number;
  addNotification: (notification: Omit<Notification, "id" | "read" | "createdAt">) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  removeNotification: (id: string) => void;
  clearAll: () => void;
}

function generateId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export const useNotificationStore = create<NotificationStore>((set) => ({
  notifications: [],
  unreadCount: 0,
  addNotification: (notification) => {
    const item: Notification = {
      ...notification,
      id: generateId(),
      read: false,
      createdAt: Date.now(),
    };
    set((state) => ({
      notifications: [item, ...state.notifications].slice(0, 50),
      unreadCount: state.unreadCount + 1,
    }));
  },
  markAsRead: (id) => {
    set((state) => {
      const notification = state.notifications.find((n) => n.id === id);
      if (!notification || notification.read) return state;
      return {
        notifications: state.notifications.map((n) =>
          n.id === id ? { ...n, read: true } : n
        ),
        unreadCount: Math.max(0, state.unreadCount - 1),
      };
    });
  },
  markAllAsRead: () => {
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, read: true })),
      unreadCount: 0,
    }));
  },
  removeNotification: (id) => {
    set((state) => {
      const notification = state.notifications.find((n) => n.id === id);
      return {
        notifications: state.notifications.filter((n) => n.id !== id),
        unreadCount: notification && !notification.read
          ? Math.max(0, state.unreadCount - 1)
          : state.unreadCount,
      };
    });
  },
  clearAll: () => {
    set({ notifications: [], unreadCount: 0 });
  },
}));
