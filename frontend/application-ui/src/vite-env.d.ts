/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_OH_BACKEND_URL?: string;
  readonly VITE_OH_WS_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
