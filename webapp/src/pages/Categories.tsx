import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronDown, ChevronRight, Plus } from "lucide-react";
import { api, Category } from "@/lib/api";
import { Hr } from "@/components/Section";

// ── Button style constants ────────────────────────────────────────────────────

const btnPrimary =
  "inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-[12.5px] font-medium bg-foreground text-background";

// ── Field row ─────────────────────────────────────────────────────────────────

function FieldRow({
  label,
  children,
  first = false,
}: {
  label: string;
  children: React.ReactNode;
  first?: boolean;
}) {
  return (
    <div
      className={
        "grid grid-cols-[88px_1fr] items-center px-3 py-2.5" +
        (first ? "" : " border-t border-[#f0f0f1]")
      }
    >
      <span className="label">{label}</span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

// ── Kind tab ──────────────────────────────────────────────────────────────────

type Kind = "expense" | "income" | "transfer";

function KindTabs({
  active,
  counts,
  onChange,
}: {
  active: Kind;
  counts: Record<Kind, number>;
  onChange: (k: Kind) => void;
}) {
  const tabs: Kind[] = ["expense", "income", "transfer"];
  return (
    <div className="flex rounded-md border border-border overflow-hidden">
      {tabs.map((k) => (
        <button
          key={k}
          onClick={() => onChange(k)}
          className={
            "flex-1 text-[11.5px] font-medium py-1.5 transition-colors capitalize " +
            (active === k
              ? "bg-foreground text-background"
              : "bg-transparent text-neutral-500 hover:bg-neutral-50")
          }
        >
          {k.charAt(0).toUpperCase() + k.slice(1)}{" "}
          <span className="opacity-60">({counts[k]})</span>
        </button>
      ))}
    </div>
  );
}

// ── Category tree helpers ─────────────────────────────────────────────────────

function buildTree(cats: Category[], kind: Kind) {
  const filtered = cats.filter((c) => c.kind === kind && !c.archived);
  const parents = filtered.filter((c) => c.parent_id == null);
  const childMap: Record<number, Category[]> = {};
  for (const c of filtered) {
    if (c.parent_id != null) {
      if (!childMap[c.parent_id]) childMap[c.parent_id] = [];
      childMap[c.parent_id].push(c);
    }
  }
  return { parents, childMap };
}

// ── Category row ─────────────────────────────────────────────────────────────

function CategoryRow({
  cat,
  children,
  isExpanded,
  onToggle,
}: {
  cat: Category;
  children?: Category[];
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const hasChildren = children && children.length > 0;
  const isMuted = false; // placeholder; no tx count in v1

  return (
    <div>
      <button
        onClick={hasChildren ? onToggle : undefined}
        className="w-full text-left flex items-center justify-between px-5 py-3 hover:bg-neutral-50 transition-colors"
      >
        <div className="flex items-center gap-2 min-w-0">
          {hasChildren ? (
            isExpanded ? (
              <ChevronDown size={13} strokeWidth={1.75} className="text-neutral-400 shrink-0" />
            ) : (
              <ChevronRight size={13} strokeWidth={1.75} className="text-neutral-400 shrink-0" />
            )
          ) : (
            <span className="w-[13px] shrink-0" />
          )}
          {cat.emoji && (
            <span className="text-[14px] leading-none shrink-0">{cat.emoji}</span>
          )}
          <span
            className={
              "text-[13px] font-semibold tracking-tight truncate" +
              (isMuted ? " text-neutral-400" : "")
            }
          >
            {cat.name}
          </span>
          {hasChildren && (
            <span className="num text-[10.5px] text-neutral-400 ml-1 shrink-0">
              {children!.length} sub
            </span>
          )}
        </div>
        {/* Placeholder expense total */}
        <span className="num text-[11px] text-neutral-400 shrink-0 ml-2">—</span>
      </button>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div className="border-t border-[#f0f0f1]">
          {children!.map((child) => (
            <div
              key={child.id}
              className="flex items-center justify-between pl-[44px] pr-5 py-2.5 hover:bg-neutral-50 transition-colors border-t border-[#f8f8f8] first:border-0"
            >
              <div className="flex items-center gap-2 min-w-0">
                {child.emoji && (
                  <span className="text-[13px] leading-none shrink-0">{child.emoji}</span>
                )}
                <span className="text-[12.5px] text-neutral-600 truncate">
                  {child.name}
                </span>
              </div>
              <span className="num text-[11px] text-neutral-400 shrink-0 ml-2">—</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

const KINDS: Kind[] = ["expense", "income", "transfer"];

export default function Categories() {
  const nav = useNavigate();
  const qc = useQueryClient();

  const [activeKind, setActiveKind] = useState<Kind>("expense");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  // ── Queries ──────────────────────────────────────────────────────────────────

  const catsQuery = useQuery({
    queryKey: ["cats"],
    queryFn: () => api.listCategories(),
    staleTime: 60_000,
  });

  const cats: Category[] = catsQuery.data ?? [];

  // ── Counts for tabs ───────────────────────────────────────────────────────────

  const counts: Record<Kind, number> = {
    expense: cats.filter((c) => c.kind === "expense" && !c.archived).length,
    income: cats.filter((c) => c.kind === "income" && !c.archived).length,
    transfer: cats.filter((c) => c.kind === "transfer" && !c.archived).length,
  };

  // ── Tree for active kind ───────────────────────────────────────────────────

  const { parents, childMap } = buildTree(cats, activeKind);

  // ── Top-level categories (for parent select in add form) ──────────────────

  const topLevelAll = cats.filter((c) => c.parent_id == null && !c.archived);

  // ── Add category form ──────────────────────────────────────────────────────

  const [catName, setCatName] = useState("");
  const [catParentId, setCatParentId] = useState<number | "">("");
  const [catKind, setCatKind] = useState<Kind>("expense");
  const [catEmoji, setCatEmoji] = useState("");

  const createMut = useMutation({
    mutationFn: () =>
      api.createCategory({
        name: catName,
        parent_id: catParentId !== "" ? Number(catParentId) : null,
        kind: catKind,
        emoji: catEmoji || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cats"] });
      setCatName("");
      setCatParentId("");
      setCatKind("expense");
      setCatEmoji("");
    },
  });

  function toggleExpand(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="pb-16">
      {/* ── Top bar ──────────────────────────────────────────────────────────── */}
      <div className="px-4 pt-4 pb-3 flex items-center justify-between">
        <button
          onClick={() => nav(-1)}
          className="w-8 h-8 flex items-center justify-center text-neutral-600 -ml-1"
          aria-label="Back"
        >
          <ChevronLeft size={20} strokeWidth={1.75} />
        </button>

        <span className="text-[13px] font-semibold tracking-tight">Categories</span>

        <button
          className="w-8 h-8 flex items-center justify-center text-neutral-600"
          aria-label="Add category"
          onClick={() =>
            document
              .getElementById("add-category-form")
              ?.scrollIntoView({ behavior: "smooth" })
          }
        >
          <Plus size={18} strokeWidth={1.75} />
        </button>
      </div>

      <Hr />

      {/* ── Kind tabs ────────────────────────────────────────────────────────── */}
      <div className="px-5 py-3">
        <KindTabs active={activeKind} counts={counts} onChange={setActiveKind} />
      </div>

      <Hr />

      {/* ── Category list ────────────────────────────────────────────────────── */}
      {catsQuery.isLoading ? (
        <div className="px-5 py-4 label">Loading…</div>
      ) : parents.length === 0 ? (
        <div className="px-5 py-4 text-[12px] text-neutral-400">
          No {activeKind} categories yet.
        </div>
      ) : (
        <div className="divide-y divide-[#f0f0f1]">
          {parents.map((cat) => (
            <CategoryRow
              key={cat.id}
              cat={cat}
              children={childMap[cat.id]}
              isExpanded={expanded.has(cat.id)}
              onToggle={() => toggleExpand(cat.id)}
            />
          ))}
        </div>
      )}

      <Hr />

      {/* ── Add category form ─────────────────────────────────────────────────── */}
      <div id="add-category-form" className="px-5 py-4">
        <div className="label mb-3">Add category</div>
        <div className="border border-border rounded-md bg-white overflow-hidden">
          <FieldRow label="Name" first>
            <input
              type="text"
              value={catName}
              onChange={(e) => setCatName(e.target.value)}
              placeholder="Category name"
              className="text-[12.5px] bg-transparent border-0 outline-none w-full placeholder:text-neutral-300"
            />
          </FieldRow>

          <FieldRow label="Parent">
            <select
              value={catParentId}
              onChange={(e) =>
                setCatParentId(
                  e.target.value === "" ? "" : Number(e.target.value)
                )
              }
              className="text-[12.5px] bg-transparent border-0 outline-none w-full"
            >
              <option value="">(top-level)</option>
              {topLevelAll.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.emoji ? `${c.emoji} ` : ""}
                  {c.name}
                </option>
              ))}
            </select>
          </FieldRow>

          <FieldRow label="Kind">
            <select
              value={catKind}
              onChange={(e) => setCatKind(e.target.value as Kind)}
              className="text-[12.5px] bg-transparent border-0 outline-none w-full"
            >
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </FieldRow>

          <FieldRow label="Emoji">
            <input
              type="text"
              value={catEmoji}
              onChange={(e) => setCatEmoji(e.target.value.slice(0, 4))}
              placeholder="🍕"
              className="text-[14px] bg-transparent border-0 outline-none w-full placeholder:text-neutral-300"
            />
          </FieldRow>
        </div>

        <button
          className={btnPrimary + " mt-3 w-full justify-center"}
          onClick={() => {
            if (!catName.trim()) return;
            createMut.mutate();
          }}
          disabled={createMut.isPending || !catName.trim()}
        >
          <Plus size={13} strokeWidth={1.75} />
          {createMut.isPending ? "Adding…" : "Add category"}
        </button>

        {createMut.isError && (
          <div className="mt-2 text-[11px] text-red-500">
            Error: {(createMut.error as Error).message}
          </div>
        )}
      </div>
    </div>
  );
}
