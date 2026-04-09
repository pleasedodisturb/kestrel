/**
 * SettingsPage — Settings page with tabbed sections for Profiles and Integrations.
 *
 * Supports:
 * - VAL-PIPE-017 (profile create/edit flow)
 * - VAL-PUSH-006 (all integrations have settings section with credential fields,
 *                  on/off toggle, status indicator)
 */

import { useState, useCallback } from "react";
import {
  useProfiles,
  useCreateProfile,
  useUpdateProfile,
  useDeleteProfile,
} from "@/hooks/useProfiles";
import type { ProfileResponse, ProfileCreate } from "@/api/profiles";
import {
  fetchIntegrations,
  updateIntegration,
  testIntegration,
} from "@/api/integrations";
import type {
  IntegrationConfigResponse,
  IntegrationConfigUpdate,
} from "@/api/integrations";
import { IntegrationPanel } from "@/components/IntegrationPanel";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  User,
  Plus,
  Pencil,
  Trash2,
  Save,
  X,
  Plug,
} from "lucide-react";

type SettingsTab = "profiles" | "integrations";

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("integrations");

  return (
    <div data-testid="settings-page" className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8" aria-label="Settings tabs">
          <button
            data-testid="tab-integrations"
            onClick={() => setActiveTab("integrations")}
            className={`whitespace-nowrap border-b-2 px-1 py-3 text-sm font-medium ${
              activeTab === "integrations"
                ? "border-gray-900 text-gray-900"
                : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
            }`}
          >
            <Plug className="mr-2 inline-block h-4 w-4" />
            Integrations
          </button>
          <button
            data-testid="tab-profiles"
            onClick={() => setActiveTab("profiles")}
            className={`whitespace-nowrap border-b-2 px-1 py-3 text-sm font-medium ${
              activeTab === "profiles"
                ? "border-gray-900 text-gray-900"
                : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
            }`}
          >
            <User className="mr-2 inline-block h-4 w-4" />
            Profiles
          </button>
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === "integrations" && <IntegrationsSection />}
      {activeTab === "profiles" && <ProfilesSection />}
    </div>
  );
}

// ========================= Integrations Section =========================

function IntegrationsSection() {
  const queryClient = useQueryClient();

  const {
    data,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["integrations"],
    queryFn: fetchIntegrations,
  });

  const [savingName, setSavingName] = useState<string | null>(null);
  const [testingName, setTestingName] = useState<string | null>(null);

  const updateMutation = useMutation({
    mutationFn: ({
      name,
      payload,
    }: {
      name: string;
      payload: IntegrationConfigUpdate;
    }) => updateIntegration(name, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
    },
    onSettled: () => {
      setSavingName(null);
    },
  });

  const handleUpdate = useCallback(
    async (name: string, payload: IntegrationConfigUpdate) => {
      setSavingName(name);
      await updateMutation.mutateAsync({ name, payload });
    },
    [updateMutation],
  );

  const handleTest = useCallback(
    async (
      name: string,
    ): Promise<{ success: boolean; message: string }> => {
      setTestingName(name);
      try {
        const result = await testIntegration(name);
        await queryClient.invalidateQueries({ queryKey: ["integrations"] });
        return { success: result.success, message: result.message };
      } catch (e) {
        return {
          success: false,
          message: (e as Error).message ?? "Test failed",
        };
      } finally {
        setTestingName(null);
      }
    },
    [queryClient],
  );

  if (isLoading) {
    return (
      <div
        data-testid="integrations-loading"
        className="flex items-center justify-center py-20"
      >
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-gray-900" />
      </div>
    );
  }

  if (error) {
    return (
      <div
        data-testid="integrations-error"
        className="py-20 text-center"
      >
        <p className="text-lg font-medium text-red-700">
          {(error as Error).message}
        </p>
      </div>
    );
  }

  const integrations = data?.integrations ?? [];

  return (
    <div data-testid="integrations-section" className="space-y-4">
      <p className="text-sm text-gray-500">
        Configure external integrations. Enable an integration, enter your
        credentials, and test the connection.
      </p>
      {integrations.map((integration: IntegrationConfigResponse) => (
        <IntegrationPanel
          key={integration.name}
          integration={integration}
          onUpdate={handleUpdate}
          onTest={handleTest}
          isSaving={savingName === integration.name}
          isTesting={testingName === integration.name}
        />
      ))}
    </div>
  );
}

// ========================= Profiles Section =========================

function ProfilesSection() {
  const { data, isLoading, error } = useProfiles();
  const createMutation = useCreateProfile();
  const updateMutation = useUpdateProfile();
  const deleteMutation = useDeleteProfile();

  const [editingId, setEditingId] = useState<number | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [formData, setFormData] = useState<ProfileCreate>({
    name: "",
    email: "",
    location: "",
    job_family: "",
  });

  const handleStartEdit = useCallback((profile: ProfileResponse) => {
    setEditingId(profile.id);
    setIsCreating(false);
    setFormData({
      name: profile.name,
      email: profile.email ?? "",
      location: profile.location ?? "",
      job_family: profile.job_family ?? "",
    });
  }, []);

  const handleStartCreate = useCallback(() => {
    setEditingId(null);
    setIsCreating(true);
    setFormData({ name: "", email: "", location: "", job_family: "" });
  }, []);

  const handleCancel = useCallback(() => {
    setEditingId(null);
    setIsCreating(false);
    setFormData({ name: "", email: "", location: "", job_family: "" });
  }, []);

  const handleSave = useCallback(() => {
    if (isCreating) {
      createMutation.mutate(formData, {
        onSuccess: () => {
          setIsCreating(false);
          setFormData({ name: "", email: "", location: "", job_family: "" });
        },
      });
    } else if (editingId !== null) {
      updateMutation.mutate(
        { id: editingId, data: formData },
        {
          onSuccess: () => {
            setEditingId(null);
            setFormData({ name: "", email: "", location: "", job_family: "" });
          },
        },
      );
    }
  }, [isCreating, editingId, formData, createMutation, updateMutation]);

  const handleDelete = useCallback(
    (id: number) => {
      deleteMutation.mutate(id);
    },
    [deleteMutation],
  );

  const handleFieldChange = useCallback(
    (field: keyof ProfileCreate, value: string) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
    },
    [],
  );

  if (isLoading) {
    return (
      <div
        data-testid="settings-loading"
        className="flex items-center justify-center py-20"
      >
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-gray-900" />
      </div>
    );
  }

  if (error) {
    return (
      <div
        data-testid="settings-error"
        className="py-20 text-center"
      >
        <p className="text-lg font-medium text-red-700">
          {(error as Error).message}
        </p>
      </div>
    );
  }

  const profiles = data?.profiles ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          Manage your user profiles for the career platform.
        </p>
        {!isCreating && editingId === null && (
          <button
            data-testid="create-profile-button"
            onClick={handleStartCreate}
            className="inline-flex items-center gap-1 rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-gray-800"
          >
            <Plus className="h-4 w-4" />
            New Profile
          </button>
        )}
      </div>

      {/* Mutation errors */}
      {(createMutation.isError ||
        updateMutation.isError ||
        deleteMutation.isError) && (
        <div
          data-testid="settings-mutation-error"
          className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700"
        >
          {(
            (createMutation.error ??
              updateMutation.error ??
              deleteMutation.error) as Error
          )?.message ?? "An error occurred"}
        </div>
      )}

      {/* Create form */}
      {isCreating && (
        <div
          data-testid="profile-create-form"
          className="rounded-lg border bg-white p-6 shadow-sm"
        >
          <h2 className="mb-4 text-lg font-semibold text-gray-900">
            Create New Profile
          </h2>
          <ProfileForm
            formData={formData}
            onChange={handleFieldChange}
            onSave={handleSave}
            onCancel={handleCancel}
            isSaving={createMutation.isPending}
            testIdPrefix="create"
          />
        </div>
      )}

      {/* Profiles list */}
      <div className="space-y-4">
        {profiles.length === 0 && !isCreating ? (
          <div
            data-testid="no-profiles"
            className="rounded-lg border border-dashed border-gray-300 p-8 text-center"
          >
            <User className="mx-auto h-12 w-12 text-gray-300" />
            <p className="mt-2 text-sm text-gray-500">
              No profiles yet. Create one to get started.
            </p>
            <button
              data-testid="create-profile-cta"
              onClick={handleStartCreate}
              className="mt-4 inline-flex items-center gap-1 rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-gray-800"
            >
              <Plus className="h-4 w-4" />
              Create Profile
            </button>
          </div>
        ) : (
          profiles.map((profile) => (
            <div
              key={profile.id}
              data-testid={`profile-card-${profile.id}`}
              className="rounded-lg border bg-white p-6 shadow-sm"
            >
              {editingId === profile.id ? (
                <div data-testid={`profile-edit-form-${profile.id}`}>
                  <h3 className="mb-4 text-lg font-semibold text-gray-900">
                    Edit Profile
                  </h3>
                  <ProfileForm
                    formData={formData}
                    onChange={handleFieldChange}
                    onSave={handleSave}
                    onCancel={handleCancel}
                    isSaving={updateMutation.isPending}
                    testIdPrefix={`edit-${profile.id}`}
                  />
                </div>
              ) : (
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <User className="h-5 w-5 text-gray-400" />
                      <h3
                        data-testid={`profile-name-${profile.id}`}
                        className="text-lg font-medium text-gray-900"
                      >
                        {profile.name}
                      </h3>
                    </div>
                    <div className="mt-2 space-y-1 text-sm text-gray-600">
                      {profile.email && (
                        <p data-testid={`profile-email-${profile.id}`}>
                          📧 {profile.email}
                        </p>
                      )}
                      {profile.location && (
                        <p data-testid={`profile-location-${profile.id}`}>
                          📍 {profile.location}
                        </p>
                      )}
                      {profile.job_family && (
                        <p data-testid={`profile-job-family-${profile.id}`}>
                          💼 {profile.job_family}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      data-testid={`edit-profile-${profile.id}`}
                      onClick={() => handleStartEdit(profile)}
                      className="inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-2 py-1 text-sm text-gray-700 hover:bg-gray-50"
                    >
                      <Pencil className="h-3 w-3" />
                      Edit
                    </button>
                    <button
                      data-testid={`delete-profile-${profile.id}`}
                      onClick={() => handleDelete(profile.id)}
                      disabled={deleteMutation.isPending}
                      className="inline-flex items-center gap-1 rounded-md border border-red-300 bg-white px-2 py-1 text-sm text-red-700 hover:bg-red-50 disabled:opacity-50"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ---- Profile Form Component ----

function ProfileForm({
  formData,
  onChange,
  onSave,
  onCancel,
  isSaving,
  testIdPrefix,
}: Readonly<{
  formData: ProfileCreate;
  onChange: (field: keyof ProfileCreate, value: string) => void;
  onSave: () => void;
  onCancel: () => void;
  isSaving: boolean;
  testIdPrefix: string;
}>) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor={`${testIdPrefix}-name-input`} className="block text-sm font-medium text-gray-700">
            Name <span className="text-red-500">*</span>
          </label>
          <input
            id={`${testIdPrefix}-name-input`}
            data-testid={`${testIdPrefix}-name-input`}
            type="text"
            value={formData.name}
            onChange={(e) => onChange("name", e.target.value)}
            placeholder="Full name"
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
          />
        </div>
        <div>
          <label htmlFor={`${testIdPrefix}-email-input`} className="block text-sm font-medium text-gray-700">
            Email
          </label>
          <input
            id={`${testIdPrefix}-email-input`}
            data-testid={`${testIdPrefix}-email-input`}
            type="email"
            value={formData.email ?? ""}
            onChange={(e) => onChange("email", e.target.value)}
            placeholder="email@example.com"
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
          />
        </div>
        <div>
          <label htmlFor={`${testIdPrefix}-location-input`} className="block text-sm font-medium text-gray-700">
            Location
          </label>
          <input
            id={`${testIdPrefix}-location-input`}
            data-testid={`${testIdPrefix}-location-input`}
            type="text"
            value={formData.location ?? ""}
            onChange={(e) => onChange("location", e.target.value)}
            placeholder="City, Country"
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
          />
        </div>
        <div>
          <label htmlFor={`${testIdPrefix}-job-family-input`} className="block text-sm font-medium text-gray-700">
            Job Family
          </label>
          <input
            id={`${testIdPrefix}-job-family-input`}
            data-testid={`${testIdPrefix}-job-family-input`}
            type="text"
            value={formData.job_family ?? ""}
            onChange={(e) => onChange("job_family", e.target.value)}
            placeholder="e.g., Senior TPM / Product Engineer"
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
          />
        </div>
      </div>
      <div className="flex items-center gap-2 pt-2">
        <button
          data-testid={`${testIdPrefix}-save-button`}
          onClick={onSave}
          disabled={isSaving || !formData.name.trim()}
          className="inline-flex items-center gap-1 rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-gray-800 disabled:opacity-50"
        >
          <Save className="h-4 w-4" />
          {isSaving ? "Saving…" : "Save"}
        </button>
        <button
          data-testid={`${testIdPrefix}-cancel-button`}
          onClick={onCancel}
          className="inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
        >
          <X className="h-4 w-4" />
          Cancel
        </button>
      </div>
    </div>
  );
}
