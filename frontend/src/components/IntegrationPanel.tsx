/**
 * IntegrationPanel — A single integration's configuration card.
 *
 * Shows: display name, description, status indicator, on/off toggle,
 * credential fields, save/test buttons.
 */

import { useState, useCallback } from "react";
import type {
  IntegrationConfigResponse,
  IntegrationConfigUpdate,
} from "@/api/integrations";
import {
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
  Settings2,
  Zap,
  Eye,
  EyeOff,
} from "lucide-react";

interface IntegrationPanelProps {
  readonly integration: IntegrationConfigResponse;
  readonly onUpdate: (name: string, data: IntegrationConfigUpdate) => Promise<void>;
  readonly onTest: (name: string) => Promise<{ success: boolean; message: string }>;
  readonly isSaving: boolean;
  readonly isTesting: boolean;
}

function StatusIndicator({
  status,
  message,
}: Readonly<{
  status: string;
  message: string | null;
}>) {
  switch (status) {
    case "connected":
      return (
        <span
          data-testid="status-connected"
          className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700"
          title={message ?? "Connected"}
        >
          <CheckCircle className="h-3 w-3" />
          Connected
        </span>
      );
    case "error":
      return (
        <span
          data-testid="status-error"
          className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700"
          title={message ?? "Error"}
        >
          <XCircle className="h-3 w-3" />
          Error
        </span>
      );
    case "disabled":
      return (
        <span
          data-testid="status-disabled"
          className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-500"
        >
          <AlertCircle className="h-3 w-3" />
          Disabled
        </span>
      );
    default:
      return (
        <span
          data-testid="status-not-configured"
          className="inline-flex items-center gap-1 rounded-full bg-yellow-50 px-2.5 py-0.5 text-xs font-medium text-yellow-700"
        >
          <AlertCircle className="h-3 w-3" />
          Not Configured
        </span>
      );
  }
}

export function IntegrationPanel({
  integration,
  onUpdate,
  onTest,
  isSaving,
  isTesting,
}: IntegrationPanelProps) {
  const [credentialValues, setCredentialValues] = useState<
    Record<string, string>
  >({});
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>(
    {},
  );
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);

  const handleToggle = useCallback(async () => {
    await onUpdate(integration.name, { enabled: !integration.enabled });
  }, [integration.name, integration.enabled, onUpdate]);

  const handleCredentialChange = useCallback(
    (key: string, value: string) => {
      setCredentialValues((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  const handleSave = useCallback(async () => {
    // Only send credentials that have been modified
    const nonEmpty: Record<string, string> = {};
    for (const [key, value] of Object.entries(credentialValues)) {
      if (value !== "") {
        nonEmpty[key] = value;
      }
    }
    if (Object.keys(nonEmpty).length > 0) {
      await onUpdate(integration.name, { credentials: nonEmpty });
      setCredentialValues({});
    }
  }, [integration.name, credentialValues, onUpdate]);

  const handleTest = useCallback(async () => {
    setTestResult(null);
    const result = await onTest(integration.name);
    setTestResult(result);
  }, [integration.name, onTest]);

  const togglePasswordVisibility = useCallback((key: string) => {
    setShowPasswords((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const hasUnsavedChanges = Object.values(credentialValues).some(
    (v) => v !== "",
  );

  return (
    <div
      data-testid={`integration-panel-${integration.name}`}
      className="rounded-lg border bg-white shadow-sm"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-3">
          <Settings2 className="h-5 w-5 text-gray-400" />
          <div>
            <h3
              data-testid={`integration-name-${integration.name}`}
              className="text-base font-semibold text-gray-900"
            >
              {integration.display_name}
            </h3>
            <p className="text-sm text-gray-500">{integration.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <StatusIndicator
            status={integration.status}
            message={integration.status_message}
          />
          {/* Toggle switch */}
          <button
            data-testid={`integration-toggle-${integration.name}`}
            onClick={handleToggle}
            disabled={isSaving}
            className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 ${
              integration.enabled ? "bg-gray-900" : "bg-gray-200"
            }`}
            role="switch"
            aria-checked={integration.enabled}
            aria-label={`Toggle ${integration.display_name}`}
          >
            <span
              className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                integration.enabled ? "translate-x-5" : "translate-x-0"
              }`}
            />
          </button>
          {/* Expand/collapse */}
          <button
            data-testid={`integration-expand-${integration.name}`}
            onClick={() => setIsExpanded(!isExpanded)}
            className="rounded-md p-1 text-gray-400 hover:text-gray-600"
            aria-label={isExpanded ? "Collapse" : "Expand"}
          >
            <svg
              className={`h-5 w-5 transition-transform ${isExpanded ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* Expandable config section */}
      {isExpanded && (
        <div
          data-testid={`integration-config-${integration.name}`}
          className="border-t px-6 py-4"
        >
          {/* Credential fields */}
          <div className="space-y-3">
            {integration.credential_fields.map((field) => (
              <div key={field.key}>
                <label htmlFor={`credential-${integration.name}-${field.key}`} className="block text-sm font-medium text-gray-700">
                  {field.label}
                  {field.required && (
                    <span className="text-red-500"> *</span>
                  )}
                  {integration.credentials_set[field.key] && (
                    <span className="ml-2 text-xs text-green-600">
                      (configured)
                    </span>
                  )}
                </label>
                <div className="relative mt-1">
                  <input
                    id={`credential-${integration.name}-${field.key}`}
                    data-testid={`credential-${integration.name}-${field.key}`}
                    type={
                      field.field_type === "password" &&
                      !showPasswords[field.key]
                        ? "password"
                        : "text"
                    }
                    value={credentialValues[field.key] ?? ""}
                    onChange={(e) =>
                      handleCredentialChange(field.key, e.target.value)
                    }
                    placeholder={
                      integration.credentials_set[field.key]
                        ? "••••••••  (leave blank to keep current)"
                        : field.placeholder
                    }
                    className="w-full rounded-md border border-gray-300 px-3 py-2 pr-10 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
                  />
                  {field.field_type === "password" && (
                    <button
                      type="button"
                      onClick={() => togglePasswordVisibility(field.key)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      tabIndex={-1}
                    >
                      {showPasswords[field.key] ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Error/status message */}
          {integration.status_message != null && integration.status === "error" && (
            <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {integration.status_message}
            </div>
          )}

          {/* Test result */}
          {testResult && (
            <div
              data-testid={`test-result-${integration.name}`}
              className={`mt-3 rounded-md px-3 py-2 text-sm ${
                testResult.success
                  ? "bg-green-50 text-green-700"
                  : "bg-red-50 text-red-700"
              }`}
            >
              {testResult.message}
            </div>
          )}

          {/* Actions */}
          <div className="mt-4 flex items-center gap-2">
            <button
              data-testid={`save-credentials-${integration.name}`}
              onClick={handleSave}
              disabled={isSaving || !hasUnsavedChanges}
              className="inline-flex items-center gap-1 rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-gray-800 disabled:opacity-50"
            >
              {isSaving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : null}
              Save Credentials
            </button>
            <button
              data-testid={`test-connection-${integration.name}`}
              onClick={handleTest}
              disabled={isTesting}
              className="inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-50"
            >
              {isTesting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Zap className="h-4 w-4" />
              )}
              Test Connection
            </button>
          </div>

          {/* Last tested */}
          {integration.last_tested_at && (
            <p className="mt-2 text-xs text-gray-400">
              Last tested:{" "}
              {new Date(integration.last_tested_at).toLocaleString()}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
