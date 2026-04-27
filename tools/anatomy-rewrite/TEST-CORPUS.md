# Test Corpus · 50 URLs for Plan D harness

Selected to exercise: adopted stylesheets, shadow DOM, canvas state, typical modern SPA patterns. NOT selected for anti-scrape adversarial testing · Plan D's win condition is the authenticated browser, not cold-fetch circumvention.

## Tier 1 · Minimum pass gate (5 URLs)
1. https://linear.app/homepage
2. https://notion.com/product
3. https://excalidraw.com/
4. https://www.anthropic.com/
5. https://www.figma.com/community

## Tier 2 · Modern SPA fidelity (15 URLs)
6. https://vercel.com/
7. https://stripe.com/
8. https://www.netlify.com/
9. https://supabase.com/
10. https://planetscale.com/
11. https://cal.com/
12. https://railway.app/
13. https://fly.io/
14. https://clerk.com/
15. https://resend.com/
16. https://tailwindcss.com/
17. https://react.dev/
18. https://nextjs.org/
19. https://astro.build/
20. https://svelte.dev/

## Tier 3 · Dashboards + Apps (10 URLs · mostly need auth)
21. https://app.posthog.com/ (auth)
22. https://github.com/anthropics/claude-code
23. https://app.netlify.com/ (auth)
24. https://dashboard.stripe.com/ (auth)
25. https://app.supabase.com/ (auth)
26. https://vercel.com/dashboard (auth)
27. https://app.clerk.com/ (auth)
28. https://console.upstash.com/ (already captured)
29. https://console.apify.com/ (already captured)
30. https://mail.google.com/ (auth, already captured)

## Tier 4 · Canvas/WebGL + adopted-heavy (10 URLs)
31. https://tldraw.com/
32. https://whimsical.com/
33. https://pixilart.com/draw
34. https://maps.google.com/
35. https://photopea.com/
36. https://app.excalidraw.com/
37. https://three.js.org/
38. https://playcanvas.com/
39. https://open-web-terminal.com/
40. https://app.eraser.io/

## Tier 5 · Content sites (10 URLs · sanity baseline)
41. https://substack.com/
42. https://medium.com/
43. https://news.ycombinator.com/ (already captured)
44. https://dev.to/
45. https://www.npmjs.com/ (already captured)
46. https://lobste.rs/
47. https://blog.vercel.com/
48. https://blog.cloudflare.com/
49. https://overreacted.io/
50. https://josephg.com/blog/

## Excluded by design (anti-scrape adversarial · not our target)
- figma.com/file/* (auth + anti-bot)
- google.com/* (anti-bot)
- twitter.com/x.com (anti-bot, API exists)
- facebook.com/instagram.com (same)
- cloudflare-challenged sites in general · Plan D runs in the extension, handles these via the user's real session

## Rationale for tier 1
Five URLs with narrow reasons, not a breadth test:
- linear.app = ONLY confirmed adopted stylesheet site in probe 02 · SPEC 01 gate
- notion.com = shadow DOM + sane JS page · SPEC 02 gate
- excalidraw.com = canvas pixel capture · SPEC 03 gate
- anthropic.com = regression baseline · simple SPA that current extension already captures well
- figma.com/community = authenticated-browser fidelity proof · current extension raw mode passed it on Bruke's click

If all three SPECs + regression baseline + authenticated-capture baseline pass on these five, the patches are ready for tier 2 broader coverage.
