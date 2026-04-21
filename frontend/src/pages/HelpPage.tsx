/**
 * HelpPage -- Getting Started for Non-Developers.
 *
 * Implements D-12 (in-app /help route), D-13 (terminal basics + Kestrel
 * commands), and D-14 (accessible from navigation, warm teaching tone).
 *
 * Single-page reference with a friendly, teaching tone -- like explaining
 * to a friend who has never used a terminal before.
 */

import { Terminal, HelpCircle, Wrench, Rocket, ArrowLeft, RotateCcw } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { DEFAULT_PROFILE_ID, resetOnboarding } from "@/api/onboarding";

function Section({
  icon: Icon,
  title,
  children,
}: Readonly<{
  icon: typeof Terminal;
  title: string;
  children: React.ReactNode;
}>) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white p-6">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100">
          <Icon className="h-5 w-5 text-gray-700" />
        </div>
        <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      </div>
      <div className="mt-4 space-y-3 text-sm leading-relaxed text-gray-700">
        {children}
      </div>
    </section>
  );
}

function CodeBlock({ children }: Readonly<{ children: string }>) {
  return (
    <pre className="rounded-md bg-gray-900 px-4 py-3 text-sm text-gray-100">
      <code>{children}</code>
    </pre>
  );
}

export function HelpPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-8 pb-16" data-testid="help-page">
      {/* Back link */}
      <Link
        to="/"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Pipeline
      </Link>

      {/* Page header */}
      <header>
        <h1 className="text-2xl font-bold text-gray-900">
          Getting Started with Kestrel
        </h1>
        <p className="mt-2 text-base text-gray-600">
          A friendly guide for people who have never used a terminal before.
          Everything here is designed to get you up and running quickly.
        </p>
      </header>

      {/* What is a terminal? */}
      <Section icon={Terminal} title="What is a terminal?">
        <p>
          Think of the terminal as a text-based way to talk to your computer.
          Instead of clicking buttons and menus, you type short commands and
          press Enter. It might feel unfamiliar at first, but you only need a
          handful of commands to use Kestrel.
        </p>
        <p className="font-medium">How to open it:</p>
        <ul className="list-inside list-disc space-y-1 text-gray-600">
          <li>
            <strong>macOS:</strong> Open Spotlight (Cmd + Space), type
            &quot;Terminal&quot;, and press Enter
          </li>
          <li>
            <strong>Ubuntu / Linux:</strong> Press Ctrl + Alt + T
          </li>
          <li>
            <strong>Windows (WSL):</strong> Search for &quot;Ubuntu&quot; or
            &quot;WSL&quot; in the Start menu
          </li>
        </ul>
        <p>
          Once the terminal is open, you will see a blinking cursor. That is
          where you type commands.
        </p>
      </Section>

      {/* Installing Kestrel */}
      <Section icon={Rocket} title="Installing Kestrel">
        <p>
          Kestrel is installed with <code className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-800">pip</code>,
          which is a tool that comes with Python. Think of it like an app store
          for Python programs.
        </p>
        <p>
          Open your terminal and type this command, then press Enter:
        </p>
        <CodeBlock>pip install kestrel-app</CodeBlock>
        <p>
          This downloads Kestrel and sets it up on your computer. It only needs
          to happen once. After that, you can use the <code className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-800">kestrel</code> command
          anytime.
        </p>
      </Section>

      {/* Key commands */}
      <Section icon={Wrench} title="Key commands">
        <p>
          Here are the commands you will use most. Type any of these into your
          terminal and press Enter:
        </p>

        <div className="space-y-4">
          <div>
            <CodeBlock>kestrel init</CodeBlock>
            <p className="mt-1 text-gray-600">
              Sets up your profile. Asks a few questions about your name,
              location, target roles, and skills. You can skip any question and
              fill it in later.
            </p>
          </div>

          <div>
            <CodeBlock>kestrel pipeline</CodeBlock>
            <p className="mt-1 text-gray-600">
              Shows your job applications in the terminal. Lists every job you
              are tracking with its current status.
            </p>
          </div>

          <div>
            <CodeBlock>kestrel doctor</CodeBlock>
            <p className="mt-1 text-gray-600">
              Checks that everything is working correctly. If something is
              wrong, it tells you exactly what to fix. Run this if you ever
              run into trouble.
            </p>
          </div>

          <div>
            <CodeBlock>kestrel init --skip</CodeBlock>
            <p className="mt-1 text-gray-600">
              For power users: creates a default profile immediately without
              asking any questions.
            </p>
          </div>
        </div>
      </Section>

      {/* Getting help */}
      <Section icon={HelpCircle} title="Need more help?">
        <p>
          If something is not working or you have a suggestion, you can reach
          us in two ways:
        </p>
        <ul className="list-inside list-disc space-y-1 text-gray-600">
          <li>
            Click the feedback button (bottom-right corner of any page) to
            open a pre-filled issue on GitHub
          </li>
          <li>
            Run <code className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-800">kestrel doctor</code> to
            diagnose common problems automatically
          </li>
        </ul>
        <p>
          Every error message in Kestrel includes what went wrong and what to
          do next. You should never see a confusing stack trace during normal
          use.
        </p>
      </Section>

      {/* Restart onboarding */}
      <RestartOnboarding />
    </div>
  );
}

function RestartOnboarding() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  return (
    <div className="mt-8 rounded-lg border border-gray-200 bg-gray-50 p-6 text-center">
      <RotateCcw className="mx-auto h-6 w-6 text-gray-400" />
      <p className="mt-2 text-sm text-gray-600">
        Want to go through the setup again? Your profile data will be kept.
      </p>
      <button
        onClick={async () => {
          await resetOnboarding(DEFAULT_PROFILE_ID);
          await queryClient.invalidateQueries({ queryKey: ["onboarding-status"] });
          navigate("/welcome");
        }}
        className="mt-3 rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100"
        data-testid="restart-onboarding-help"
      >
        Restart onboarding
      </button>
    </div>
  );
}
