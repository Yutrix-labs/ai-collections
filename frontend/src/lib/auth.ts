const AUTH_KEY = "ca_auth";
const CORRECT_PIN = "123456";

export function isLoggedIn(): boolean {
  if (typeof window === "undefined") return false;
  return sessionStorage.getItem(AUTH_KEY) === "1";
}

export function tryLogin(pin: string): boolean {
  if (pin === CORRECT_PIN) {
    sessionStorage.setItem(AUTH_KEY, "1");
    return true;
  }
  return false;
}

export function logout(): void {
  sessionStorage.removeItem(AUTH_KEY);
}
