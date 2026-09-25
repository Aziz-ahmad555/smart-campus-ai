# Sentra frontend

React 19 + Vite + Tailwind CSS v4 dashboard for Smart Campus AI. See the [project README](../README.md) for the full system.

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production build in dist/
npm run lint     # oxlint
```

The backend address defaults to `http://localhost:8000`. To change it, copy `.env.example` to `.env` and set `VITE_API_URL`.

## Structure

| Folder | Contents |
|---|---|
| `src/pages/` | One component per screen: landing, login, dashboard, students, staff, classes, visitors, my class, my profile, 404 |
| `src/components/ui/` | Design system: `Button`, `Input`/`Select`, `Modal`/`ConfirmDialog`, `Badge`, `Card`, `Table`, `StatCard`, `Tabs`, toasts, empty/error/loading states |
| `src/components/layout/` | `AppShell`: role-aware sidebar, mobile menu, theme toggle, fingerprint setup, sign-out |
| `src/components/dashboard/` | Camera feed, foot-traffic chart, event log |
| `src/lib/` | API client (`api.js`), session storage, theme, `useApi` and `useLiveEvents` hooks, formatting helpers |

## Conventions

- All requests go through `lib/api.js`; authenticated calls pass `{ auth: true }`.
- Every data view has a loading state, an empty state, and an error state with retry.
- Confirmations use `ConfirmDialog` and feedback uses toasts, never `window.alert` or `window.confirm`.
- Colours carry meaning: green for entries and on-campus, amber for crowd alerts, red for falls, overstays and destructive actions.
- The theme follows the OS until the user picks one; the choice is saved in `localStorage`.
