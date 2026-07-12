// inPACT runtime config — copy to js/config.js and fill in your project.
// js/config.js is gitignored: it holds environment-specific values, not
// secrets in the strict sense (the anon key is safe to ship to a browser;
// row-level security is what actually protects the data — see
// migrations/006_inpact_mvp.sql). Keeping it out of git just avoids
// hardcoding one Supabase project into the shared app.
//
// Values come from: Supabase dashboard -> Project Settings -> API.

window.INPACT_CONFIG = {
  SUPABASE_URL: 'https://YOUR-PROJECT.supabase.co',
  SUPABASE_ANON_KEY: 'YOUR-ANON-PUBLIC-KEY',
  // Set in block F (Stripe). Leave blank for block B/C/D/E.
  STRIPE_PUBLISHABLE_KEY: '',
};
