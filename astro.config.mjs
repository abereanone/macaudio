import { defineConfig } from "astro/config";
import cloudflare from "@astrojs/cloudflare";

// Astro on Cloudflare, SSR. Bindings (D1, R2, env) via Astro.locals.runtime.env.
export default defineConfig({
  output: "server",
  adapter: cloudflare({
    platformProxy: { enabled: true },
    imageService: "compile",
  }),
  site: "https://teaching.michaelcoughlin.net",
});
