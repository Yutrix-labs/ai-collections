import { authApi } from "@/auth/authApi";

/** Ends the auth-bff session (and clears the cookie). */
export async function logout(): Promise<void> {
  await authApi.logout();
}
