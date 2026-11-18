// Resolution stub for lucide-react under Vitest - see vitest.config.ts's
// alias entry. lucide-react@1.74.0's published package omits
// dist/esm/lucide-react.mjs (only per-icon files exist under
// dist/esm/icons/), which Vite's resolver can't follow via the package's
// "module"/"import" export condition - a packaging quirk Next.js's own
// (Turbopack/webpack) resolution tolerates but Vite does not. Icons are
// purely decorative in this app, so every icon name actually imported
// anywhere in src/ resolves to a trivial stub component for tests. A
// dynamic Proxy doesn't work here: Vite's commonjs interop needs static,
// named exports to synthesize ESM named imports, so each one is listed
// explicitly - add a new icon's name here if a future import needs it (a
// missing one fails fast and loudly with an import error, not a silent
// `undefined` render).

const Icon = () => null;

export default Icon;
export {
  Icon as Activity,
  Icon as AlertTriangle,
  Icon as ArrowLeft,
  Icon as ArrowUpRight,
  Icon as Bot,
  Icon as Check,
  Icon as CheckCircle2,
  Icon as ChevronDown,
  Icon as ChevronLeft,
  Icon as ChevronRight,
  Icon as Circle,
  Icon as Cloud,
  Icon as Code2,
  Icon as Command,
  Icon as Copy,
  Icon as FolderTree,
  Icon as GitBranch,
  Icon as Inbox,
  Icon as KeyRound,
  Icon as Layers,
  Icon as LayoutDashboard,
  Icon as LogOut,
  Icon as Plug,
  Icon as Plus,
  Icon as Search,
  Icon as Settings,
  Icon as ShieldCheck,
  Icon as Terminal,
  Icon as Trash2,
  Icon as Users,
  Icon as Workflow,
  Icon as X,
};
