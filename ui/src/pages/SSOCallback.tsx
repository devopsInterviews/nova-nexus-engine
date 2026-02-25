/**
 * SSO Callback Page
 *
 * This page handles the final step of the OIDC Authorization Code flow.
 * After the backend validates the Authentik callback and issues a portal
 * JWT, it redirects the browser here:
 *
 *   /sso/callback?token=<portal-jwt>
 *
 * This component:
 * 1. Extracts the token from the URL query string.
 * 2. Stores it in localStorage (same key as the local login flow).
 * 3. Fetches the user profile from /api/me using the new token.
 * 4. Updates the AuthContext so the app instantly recognises the user.
 * 5. Navigates to the home page.
 *
 * If any step fails (missing token, invalid token, network error) the
 * user is redirected back to /login with an error message.
 */

import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/context/auth-context";

const API_BASE_URL = "/api";

export default function SSOCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { setSSOSession } = useAuth();
  const [status, setStatus] = useState<"processing" | "error">("processing");
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    const processCallback = async () => {
      const token = searchParams.get("token");

      if (!token) {
        console.error("[SSOCallback] No token found in query string");
        setStatus("error");
        setErrorMessage("No authentication token received. Please try again.");
        setTimeout(() => navigate("/login?sso_error=No+token+received", { replace: true }), 2000);
        return;
      }

      console.log("[SSOCallback] Token received, fetching user profile…");

      try {
        const response = await fetch(`${API_BASE_URL}/me`, {
          method: "GET",
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) {
          throw new Error(`Profile fetch failed with HTTP ${response.status}`);
        }

        const userData = await response.json();
        console.log("[SSOCallback] User profile fetched:", userData.username);

        // Persist in localStorage and update AuthContext
        setSSOSession(token, userData);

        console.log("[SSOCallback] SSO login complete — redirecting to home");
        navigate("/", { replace: true });
      } catch (err) {
        console.error("[SSOCallback] Failed to complete SSO login:", err);
        setStatus("error");
        setErrorMessage("Failed to complete authentication. Please try again.");
        setTimeout(() => navigate("/login?sso_error=Authentication+failed", { replace: true }), 2500);
      }
    };

    processCallback();
  }, [searchParams, navigate, setSSOSession]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-surface to-surface-elevated">
      <div className="text-center space-y-4">
        {status === "processing" ? (
          <>
            <div className="mx-auto w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin" />
            <h2 className="text-xl font-semibold text-foreground">
              Completing sign-in…
            </h2>
            <p className="text-muted-foreground">
              Please wait while we set up your session.
            </p>
          </>
        ) : (
          <>
            <div className="mx-auto w-12 h-12 flex items-center justify-center rounded-full bg-red-500/10 text-red-500 text-2xl">
              !
            </div>
            <h2 className="text-xl font-semibold text-foreground">
              Authentication Error
            </h2>
            <p className="text-muted-foreground">{errorMessage}</p>
            <p className="text-sm text-muted-foreground">
              Redirecting to login…
            </p>
          </>
        )}
      </div>
    </div>
  );
}
