import { useContext } from "react";
import { AuthContext } from "@/contexts/auth-context-instance";

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
