import { createContext } from "react";
import type { AuthState } from "./auth-context.types";

export const AuthContext = createContext<AuthState | undefined>(undefined);
