<template>
  <BaseDialog
    v-model="dialog"
    :title="isEdit ? $t('group.ai-provider-settings.edit-provider') : $t('group.ai-provider-settings.create-provider')"
    :icon="$globals.icons.robot"
    :loading="loading"
    can-submit
    :submit-icon="isEdit ? $globals.icons.save : $globals.icons.createAlt"
    :submit-text="isEdit ? $t('general.update') : $t('general.create')"
    :submit-disabled="submitDisabled"
    @submit="handleSubmit"
    @close="resetForm"
  >
    <v-card-text v-if="init" style="max-height: 70vh; overflow-y: auto;">
      <v-form ref="form" v-no-autofill>
        <v-btn-toggle
          v-model="providerType"
          mandatory
          divided
          density="compact"
          color="primary"
          class="mb-4 d-flex"
          @update:model-value="onProviderTypeChange"
        >
          <v-btn value="gemini" class="flex-grow-1">
            Google Gemini
          </v-btn>
          <v-btn value="openai" class="flex-grow-1">
            OpenAI
          </v-btn>
          <v-btn value="custom" class="flex-grow-1">
            Custom
          </v-btn>
        </v-btn-toggle>

        <v-text-field
          v-model="formData.name"
          :label="$t('group.ai-provider-settings.provider-name')"
          :rules="[validators.required]"
          density="compact"
          variant="outlined"
          class="mb-4"
        />

        <div class="d-flex align-start ga-2 mb-4">
          <v-combobox
            v-model="formData.model"
            :items="availableModelItems"
            item-title="title"
            item-value="value"
            :return-object="false"
            :label="$t('group.ai-provider-settings.model')"
            :hint="$t('group.ai-provider-settings.model-description')"
            :rules="[validators.required]"
            density="compact"
            variant="outlined"
            class="flex-grow-1"
          />
          <v-btn
            variant="tonal"
            color="primary"
            class="mt-1"
            :loading="fetchingModels"
            :disabled="fetchModelsDisabled || fetchingModels"
            @click="handleFetchModels"
          >
            Fetch Models
          </v-btn>
        </div>
        <v-text-field
          v-model="formData.apiKey"
          :label="$t('group.ai-provider-settings.api-key')"
          :hint="$t(
            isEdit
              ? 'group.ai-provider-settings.api-key-description-edit'
              : 'group.ai-provider-settings.api-key-description-create',
          )"
          :persistent-hint="isEdit"
          :rules="isEdit ? [] : [validators.required]"
          density="compact"
          variant="outlined"
          type="password"
          class="mb-4"
        />
        <v-text-field
          v-model="formData.baseUrl"
          :label="$t('group.ai-provider-settings.base-url')"
          :hint="$t('group.ai-provider-settings.base-url-description')"
          density="compact"
          variant="outlined"
          class="mb-4"
        />
        <v-number-input
          v-model.number="formData.timeout"
          :label="$t('group.ai-provider-settings.request-timeout-seconds')"
          type="number"
          :min="0"
          hide-details
          density="compact"
          variant="outlined"
          class="mb-4"
        />
        <v-expansion-panels v-model="advancedPanel" variant="accordion">
          <v-expansion-panel>
            <v-expansion-panel-title class="text-subtitle-2" expand-icon="$expand" collapse-icon="$expand">
              {{ $t('search.advanced') }}
            </v-expansion-panel-title>
            <v-expansion-panel-text class="px-0">
              <div class="mb-2 text-subtitle-2">
                {{ $t('group.ai-provider-settings.request-headers') }}
              </div>
              <BaseKeyValueEditor
                v-model="formData.requestHeaders"
                class="mb-4"
              />
              <v-divider class="mb-4" />
              <div class="mb-2 text-subtitle-2">
                {{ $t('group.ai-provider-settings.request-params') }}
              </div>
              <BaseKeyValueEditor
                v-model="formData.requestParams"
              />
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>

        <v-alert
          v-if="testResult"
          :type="testResult.success ? 'success' : 'error'"
          density="compact"
          variant="tonal"
          class="mt-4"
        >
          {{ connectionMessage }}{{ imageSupportMessage }}
        </v-alert>
      </v-form>
    </v-card-text>
    <AppLoader v-else />

    <template #custom-card-action>
      <v-btn
        variant="text"
        :loading="testing"
        :disabled="submitDisabled || testing"
        @click="handleTest"
      >
        {{ $t('group.ai-provider-settings.test-connection') }}
      </v-btn>
    </template>
  </BaseDialog>
</template>

<script setup lang="ts">
import { useAIProviders } from "~/composables/use-ai-providers";
import { validators } from "~/composables/use-validators";
import type { AIProviderCreate, AIProviderTestResult, AIProviderUpdate } from "~/lib/api/types/group";

const props = withDefaults(defineProps<{
  providerId?: string;
}>(), {
  providerId: undefined,
});

const emit = defineEmits<{
  (e: "create", data: AIProviderCreate): void;
  (e: "update", id: string, data: AIProviderUpdate): void;
}>();

const dialog = defineModel<boolean>({ default: false });

const { $globals } = useNuxtApp();
const i18n = useI18n();
const { loading, getOne, testOne, testSavedOne, getModels } = useAIProviders();
const init = ref(false);

const form = ref();
const advancedPanel = ref<number | undefined>(undefined);

const isEdit = computed(() => !!props.providerId);
const providerType = ref("gemini");
const availableModels = ref<Array<{ id: string; name: string; description?: string | null }>>([]);
const fetchingModels = ref(false);

const fetchModelsDisabled = computed(() => {
  return !formData.apiKey?.trim() && !isEdit.value;
});

const availableModelItems = computed(() => {
  if (availableModels.value.length > 0) {
    return availableModels.value.map(m => ({
      title: m.name ? `${m.name} (${m.id})` : m.id,
      value: m.id,
    }));
  }
  if (providerType.value === "gemini") {
    return [
      { title: "Gemini 2.5 Flash", value: "gemini-2.5-flash" },
      { title: "Gemini 2.5 Pro", value: "gemini-2.5-pro" },
      { title: "Gemini 2.0 Flash", value: "gemini-2.0-flash" },
      { title: "Gemini 1.5 Flash", value: "gemini-1.5-flash" },
      { title: "Gemini 1.5 Pro", value: "gemini-1.5-pro" },
    ];
  }
  return [
    { title: "gpt-4o", value: "gpt-4o" },
    { title: "gpt-4o-mini", value: "gpt-4o-mini" },
  ];
});

function onProviderTypeChange(type: string) {
  if (type === "gemini") {
    if (!formData.name || formData.name === "OpenAI" || formData.name === "Custom") {
      formData.name = "Google Gemini";
    }
    formData.baseUrl = "https://generativelanguage.googleapis.com/v1beta/openai/";
    if (!formData.model || formData.model === "gpt-4o" || formData.model === "gpt-4o-mini") {
      formData.model = "gemini-2.5-flash";
    }
  }
  else if (type === "openai") {
    if (!formData.name || formData.name === "Google Gemini" || formData.name === "Custom") {
      formData.name = "OpenAI";
    }
    formData.baseUrl = "https://api.openai.com/v1";
    if (!formData.model || formData.model.startsWith("gemini")) {
      formData.model = "gpt-4o";
    }
  }
  else {
    if (!formData.name || formData.name === "Google Gemini" || formData.name === "OpenAI") {
      formData.name = "Custom";
    }
    formData.baseUrl = "";
  }
  availableModels.value = [];
}

async function handleFetchModels() {
  fetchingModels.value = true;
  try {
    const res = await getModels({
      apiKey: formData.apiKey || undefined,
      baseUrl: formData.baseUrl || null,
      providerType: providerType.value,
      providerId: props.providerId,
    });
    if (res?.data?.models && res.data.models.length > 0) {
      availableModels.value = res.data.models;
      if (!formData.model || !availableModels.value.some(m => m.id === formData.model)) {
        formData.model = availableModels.value[0].id;
      }
    }
  }
  catch (e) {
    // handled gracefully
  }
  finally {
    fetchingModels.value = false;
  }
}

const defaultForm = () => ({
  name: "Google Gemini",
  model: "gemini-2.5-flash",
  apiKey: "",
  baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai/",
  timeout: 300,
  requestHeaders: {} as Record<string, string>,
  requestParams: {} as Record<string, string>,
});

const formData = reactive(defaultForm());

const testing = ref(false);
const testResult = ref<AIProviderTestResult | null>(null);

const submitDisabled = computed(() => {
  return !formData.name?.trim() || !formData.model?.trim() || (!isEdit.value && !formData.apiKey?.trim());
});

const connectionMessage = computed(() => {
  const result = testResult.value;
  if (!result) return "";
  if (result.success) return i18n.t("group.ai-provider-settings.test-connection-succeeded");
  return result.message || i18n.t("group.ai-provider-settings.test-connection-failed");
});

const imageSupportMessage = computed(() => {
  const result = testResult.value;
  if (!result?.success || typeof result.supportsImages !== "boolean") return "";
  return result.supportsImages
    ? ` — ${i18n.t("group.ai-provider-settings.supports-images")}`
    : ` — ${i18n.t("group.ai-provider-settings.text-only-provider")}`;
});

// Fetch existing provider when editing; reset form for create mode
let requestToken = 0;

watch(
  () => [dialog.value, props.providerId] as const,
  async ([open, id]) => {
    const token = ++requestToken;
    if (!open) return;
    testResult.value = null;
    availableModels.value = [];
    if (!id) {
      resetForm();
      init.value = true;
      return;
    }
    init.value = false;
    const { data } = await getOne(id);
    if (token !== requestToken) return;
    init.value = true;
    if (data) {
      formData.name = data.name;
      formData.model = data.model;
      formData.apiKey = "";
      formData.baseUrl = data.baseUrl ?? "";
      formData.timeout = data.timeout ?? 300;
      formData.requestHeaders = { ...(data.requestHeaders ?? {}) };
      formData.requestParams = { ...(data.requestParams ?? {}) };

      if (data.baseUrl?.includes("googleapis.com") || data.name.toLowerCase().includes("gemini")) {
        providerType.value = "gemini";
      }
      else if (data.baseUrl?.includes("openai.com") || data.name.toLowerCase().includes("openai")) {
        providerType.value = "openai";
      }
      else {
        providerType.value = "custom";
      }
    }
  },
  { immediate: true },
);

function handleSubmit() {
  // Required field guard (button is also disabled, but keep as a safeguard)
  if (!formData.name?.trim() || !formData.model?.trim()) return;
  if (!isEdit.value && !formData.apiKey?.trim()) return;

  if (isEdit.value && props.providerId) {
    const payload: AIProviderUpdate & { apiKey?: string } = {
      name: formData.name,
      model: formData.model,
      baseUrl: formData.baseUrl || null,
      timeout: formData.timeout,
      requestHeaders: Object.keys(formData.requestHeaders).length ? formData.requestHeaders : undefined,
      requestParams: Object.keys(formData.requestParams).length ? formData.requestParams : undefined,
    };
    if (formData.apiKey) {
      payload.apiKey = formData.apiKey;
    }
    emit("update", props.providerId, payload);
  }
  else {
    const createPayload = {
      name: formData.name,
      model: formData.model,
      apiKey: formData.apiKey,
      baseUrl: formData.baseUrl || null,
      timeout: formData.timeout,
      requestHeaders: Object.keys(formData.requestHeaders).length ? formData.requestHeaders : undefined,
      requestParams: Object.keys(formData.requestParams).length ? formData.requestParams : undefined,
    };
    emit("create", createPayload as AIProviderCreate);
  }
}

function resetForm() {
  Object.assign(formData, defaultForm());
  providerType.value = "gemini";
  availableModels.value = [];
  form.value?.reset();
  advancedPanel.value = undefined;
  testResult.value = null;
}

async function handleTest() {
  testing.value = true;
  testResult.value = null;
  try {
    let data: AIProviderTestResult | null;
    if (isEdit.value && props.providerId) {
      // Test the form's CURRENT values, not what's saved in the DB — the user may have just
      // changed the model/base_url. If they left the API key blank (meaning "keep the existing
      // one"), the backend falls back to the saved key since we don't have that value here.
      const overrides: AIProviderUpdate & { apiKey?: string } = {
        name: formData.name,
        model: formData.model,
        baseUrl: formData.baseUrl || null,
        timeout: formData.timeout,
        requestHeaders: Object.keys(formData.requestHeaders).length ? formData.requestHeaders : undefined,
        requestParams: Object.keys(formData.requestParams).length ? formData.requestParams : undefined,
      };
      if (formData.apiKey) {
        overrides.apiKey = formData.apiKey;
      }
      ({ data } = await testSavedOne(props.providerId, overrides));
    }
    else {
      ({ data } = await testOne({
        name: formData.name,
        model: formData.model,
        apiKey: formData.apiKey,
        baseUrl: formData.baseUrl || null,
        timeout: formData.timeout,
        requestHeaders: Object.keys(formData.requestHeaders).length ? formData.requestHeaders : undefined,
        requestParams: Object.keys(formData.requestParams).length ? formData.requestParams : undefined,
      } as AIProviderCreate));
    }

    testResult.value = data;
  }
  finally {
    testing.value = false;
  }
}
</script>
