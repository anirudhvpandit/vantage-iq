import { useState, type FormEvent } from "react";
import { useForm } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import type { UseFormRegisterReturn } from "react-hook-form";
import { z } from "zod";
import { Gauge, ShieldCheck } from "lucide-react";
import { useAuth } from "./auth";
import { request } from "./api";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});
const registrationSchema = loginSchema.extend({
  organization_name: z.string().trim().min(2, "Enter your organization name.").max(160),
  password: z.string().min(12, "Use at least 12 characters."),
});
type LoginValues = z.infer<typeof loginSchema>;
type RegistrationValues = z.infer<typeof registrationSchema>;

export default function AuthPage() {
  const location = useLocation();
  const isRegister = location.pathname === "/register";
  const pathname = location.pathname;
  const isVerifyEmail = pathname === "/verify-email";
  const isPasswordReset = pathname === "/reset-password";
  const isForgotPassword = pathname === "/forgot-password";
  const isResendVerification = pathname === "/resend-verification";
  const isAccountAction = isVerifyEmail || isPasswordReset || isForgotPassword || isResendVerification;
  const actionToken = new URLSearchParams(location.search).get("token") ?? "";
  const navigate = useNavigate();
  const { session, isLoading, error: sessionError, login, register } = useAuth();
  const registrationQuery = useQuery({
    queryKey: ["public-config"],
    queryFn: () => request<{ registration_enabled: boolean }>("/api/v1/config"),
    retry: false,
  });
  const registrationEnabled = registrationQuery.data?.registration_enabled === true;
  const [requestError, setRequestError] = useState("");
  const [requestNotice, setRequestNotice] = useState("");
  const [actionEmail, setActionEmail] = useState("");
  const [actionPassword, setActionPassword] = useState("");
  const [actionPending, setActionPending] = useState(false);

  const loginForm = useForm<LoginValues>({ resolver: zodResolver(loginSchema), defaultValues: { email: "", password: "" } });
  const registrationForm = useForm<RegistrationValues>({
    resolver: zodResolver(registrationSchema),
    defaultValues: { email: "", password: "", organization_name: "" },
  });
  if (isLoading) return <div className="auth-loading"><span className="loading-spinner" />Checking your session…</div>;
  if (session) return <Navigate to="/app/overview" replace />;
  if (sessionError) return <div className="auth-loading" role="alert">Could not verify session: {sessionError}. Refresh to try again.</div>;

  async function submitLogin(values: LoginValues) {
    setRequestError("");
    try { await login(values); navigate("/app/overview", { replace: true }); }
    catch (error) { setRequestError(error instanceof Error ? error.message : "Sign-in failed."); }
  }
  async function submitRegistration(values: RegistrationValues) {
    setRequestError("");
    setRequestNotice("");
    try {
      await register(values);
      setRequestNotice("If the account can be created, check your inbox for a verification link. If it does not arrive, retry verification later.");
    } catch (error) { setRequestError(error instanceof Error ? error.message : "Account creation failed."); }
  }

  async function submitAccountAction(path: string, payload: object, success: string) {
    setRequestError("");
    setRequestNotice("");
    setActionPending(true);
    try {
      await request(path, { method: "POST", body: JSON.stringify(payload) });
      setRequestNotice(success);
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : "The request could not be completed.");
    } finally {
      setActionPending(false);
    }
  }

  const handleAccountAction = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isVerifyEmail) {
      if (!actionToken) {
        setRequestError("This verification link is missing its token.");
        return;
      }
      void submitAccountAction("/auth/verify-email", { token: actionToken }, "Your email is verified. You can now sign in.");
    } else if (isPasswordReset) {
      if (!actionToken) {
        setRequestError("This password reset link is missing its token.");
        return;
      }
      if (actionPassword.length < 12) {
        setRequestError("Use at least 12 characters for your new password.");
        return;
      }
      void submitAccountAction("/auth/password-reset/complete", { token: actionToken, password: actionPassword }, "Your password has been reset. You can now sign in.");
    } else if (isForgotPassword) {
      void submitAccountAction("/auth/password-reset/request", { email: actionEmail }, "If the account exists and email delivery is available, reset instructions will arrive by email.");
    } else {
      void submitAccountAction("/auth/verification/resend", { email: actionEmail }, "If the account requires verification and email delivery is available, a new link will arrive by email.");
    }
  };

  const title = isRegister ? "Create your workspace"
    : isVerifyEmail ? "Verify your email"
      : isPasswordReset ? "Choose a new password"
        : isForgotPassword ? "Reset your password"
          : isResendVerification ? "Resend verification"
            : "Welcome back";

  return (
    <main className="auth-shell">
      <section className="auth-brand-panel">
        <div className="auth-brand"><span className="auth-brand-mark"><Gauge size={22} /></span><span>vantage<strong>iq</strong></span></div>
        <div className="auth-pitch"><div className="auth-eyebrow">EXECUTIVE BUSINESS INTELLIGENCE</div><h1>See the business.<br />Understand the signals.<br /><span>Act with confidence.</span></h1><p>A decision-ready view of financial performance, customer contribution, and delivery health.</p></div>
        <div className="auth-trust"><ShieldCheck size={16} /><span>Secure, organization-scoped workspaces</span></div>
      </section>
      <section className="auth-form-panel">
        <div className="auth-form-wrap">
          <div className="auth-form-kicker">VANTAGE IQ WORKSPACE</div>
          <h2>{title}</h2>
          <p className="auth-subheading">{isRegister ? "Set up an organization and invite your team later."
            : isVerifyEmail ? "Use the secure link sent to your email address."
              : isPasswordReset ? "Choose a strong password with at least 12 characters."
                : isForgotPassword ? "Enter your account email and we’ll send reset instructions if it exists."
                  : isResendVerification ? "Request another email verification link."
                    : "Sign in to continue to your organization."}</p>
          {requestError && <div className="auth-error" role="alert">{requestError}</div>}
          {requestNotice && <div className="auth-subheading" role="status">{requestNotice}</div>}
          {isRegister && registrationQuery.isError && <div className="auth-error" role="alert">Could not load account registration settings. Refresh to try again.</div>}
          {isAccountAction ? (
            <form className="auth-form" onSubmit={handleAccountAction} noValidate>
              {(isForgotPassword || isResendVerification) && (
                <label className="auth-field" htmlFor="action-email"><span>Work email</span><input id="action-email" type="email" autoComplete="email" required value={actionEmail} onChange={(event) => setActionEmail(event.target.value)} /></label>
              )}
              {isPasswordReset && (
                <label className="auth-field" htmlFor="action-password"><span>New password</span><input id="action-password" type="password" autoComplete="new-password" required minLength={12} value={actionPassword} onChange={(event) => setActionPassword(event.target.value)} /></label>
              )}
              <button className="button button-primary auth-submit" disabled={actionPending}>
                {actionPending ? "Please wait…" : isVerifyEmail ? "Verify email" : isPasswordReset ? "Reset password" : isForgotPassword ? "Send reset link" : "Send verification link"}
              </button>
            </form>
          ) : isRegister && !registrationQuery.isError && !registrationEnabled ? (
            <div className="auth-subheading">{registrationQuery.isPending ? "Checking account registration…" : "Account creation is not enabled. Contact your organization administrator."}</div>
          ) : isRegister ? (
            <form className="auth-form" onSubmit={registrationForm.handleSubmit(submitRegistration)} noValidate>
              <FormField label="Organization" name="organization_name" error={registrationForm.formState.errors.organization_name?.message} register={registrationForm.register("organization_name")} autoComplete="organization" />
              <FormField label="Work email" name="email" type="email" error={registrationForm.formState.errors.email?.message} register={registrationForm.register("email")} autoComplete="email" />
              <FormField label="Password" name="password" type="password" error={registrationForm.formState.errors.password?.message} register={registrationForm.register("password")} autoComplete="new-password" />
              <button className="button button-primary auth-submit" disabled={registrationForm.formState.isSubmitting}>Create account</button>
            </form>
          ) : (
            <form className="auth-form" onSubmit={loginForm.handleSubmit(submitLogin)} noValidate>
              <FormField label="Work email" name="email" type="email" error={loginForm.formState.errors.email?.message} register={loginForm.register("email")} autoComplete="email" />
              <FormField label="Password" name="password" type="password" error={loginForm.formState.errors.password?.message} register={loginForm.register("password")} autoComplete="current-password" />
              <button className="button button-primary auth-submit" disabled={loginForm.formState.isSubmitting}>Sign in</button>
            </form>
          )}
          {!isAccountAction && !isRegister && <div className="auth-switch"><Link to="/forgot-password">Forgot password?</Link><span> · </span><Link to="/resend-verification">Resend verification</Link></div>}
          {(isAccountAction || isRegister || registrationEnabled) && <div className="auth-switch">{isRegister ? "Already have an account?" : "Return to"} <Link to="/login">Sign in</Link></div>}
          <div className="auth-legal">By continuing, you agree to your organization’s data-use and security policies.</div>
        </div>
      </section>
    </main>
  );
}

function FormField({ label, name, type = "text", error, register, autoComplete }: {
  label: string; name: string; type?: string; error?: string; register: UseFormRegisterReturn; autoComplete: string;
}) {
  return <label className="auth-field" htmlFor={name}><span>{label}</span><input id={name} type={type} autoComplete={autoComplete} aria-invalid={Boolean(error)} aria-describedby={error ? `${name}-error` : undefined} {...register} />{error && <small id={`${name}-error`} className="field-error">{error}</small>}</label>;
}
