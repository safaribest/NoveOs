import { post, get } from "@/lib/api";

export interface LoginResponse {
  access_token: string;
  token_type: string;
  username: string;
}

export interface UserInfo {
  username: string;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  return post<LoginResponse>("/auth/login", { username, password });
}

export async function getMe(): Promise<UserInfo> {
  return get<UserInfo>("/auth/me");
}
