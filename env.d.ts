/// <reference types="astro/client" />

type Env = {
  DB: D1Database;
  MEDIA: R2Bucket;
  SESSION: KVNamespace;
  SITE_NAME?: string;
  SITE_SHORT_NAME?: string;
  SITE_URL?: string;
  MEDIA_BASE_URL?: string;
};

type Runtime = import("@astrojs/cloudflare").Runtime<Env>;

declare namespace App {
  interface Locals extends Runtime {}
}
