/**
 * AdminDashboard.jsx — Super Admin Dashboard
 *
 * Three tabs: Overview, Users, Feedback Queue
 * Protected by role check (super_admin / admin)
 * Theme: Wine/Gold warm palette matching app design system
 */

import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  Loader2, Users, BarChart3, MessageSquareWarning, Search,
  UserPlus, ShieldCheck, Shield, User as UserIcon, ChevronRight,
  ArrowLeft, Flag, X, Clock, Eye, Gamepad2, Brain, BookOpen, Download, Copy, Check,
  Sparkles,
} from "lucide-react";
import { Chessboard } from "react-chessboard";

const WINE = "#722F37";
const GOLD_TEXT = "#8B6F1F";
const GOLD_BG = "rgba(203,161,53,0.1)";
const BORDER = "hsl(35 10% 87%)";

export default function AdminDashboard({ user }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get("tab") || "overview");

  // Admin surface is locked to the owner email — defence-in-depth on
  // top of the role check the API enforces.
  const ADMIN_EMAILS = new Set(["bhutramohit@gmail.com"]);
  const userEmail = (user?.email || "").trim().toLowerCase();
  const isAdminUser =
    user
    && (user.role === "super_admin" || user.role === "admin")
    && ADMIN_EMAILS.has(userEmail);

  if (user && !isAdminUser) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]" data-testid="admin-forbidden">
          <p className="text-sm" style={{ color: WINE }}>Access denied.</p>
        </div>
      </Layout>
    );
  }

  const handleTab = (tab) => {
    setActiveTab(tab);
    setSearchParams(tab === "overview" ? {} : { tab });
  };

  const tabs = [
    { key: "overview", label: "Overview", icon: <BarChart3 className="w-3.5 h-3.5" /> },
    { key: "users", label: "Users", icon: <Users className="w-3.5 h-3.5" /> },
    { key: "feedback", label: "Feedback", icon: <MessageSquareWarning className="w-3.5 h-3.5" /> },
    { key: "review", label: "Review", icon: <Sparkles className="w-3.5 h-3.5" /> },
  ];

  return (
    <Layout user={user}>
      <div className="max-w-4xl mx-auto py-6 px-4 space-y-6" data-testid="admin-dashboard">
        {/* Header */}
        <div>
          <h1 className="text-2xl text-foreground tracking-tight font-heading">
            Admin Dashboard
          </h1>
          <div className="flex gap-0.5 mt-4 border-b" style={{ borderColor: BORDER }} data-testid="admin-tabs">
            {tabs.map((t) => (
              <button
                key={t.key}
                className="px-4 py-2 text-sm font-light transition-colors flex items-center gap-1.5 relative"
                style={{
                  color: activeTab === t.key ? WINE : undefined,
                  borderBottom: activeTab === t.key ? `2px solid ${WINE}` : "2px solid transparent",
                  marginBottom: "-1px",
                }}
                onClick={() => handleTab(t.key)}
                data-testid={`admin-tab-${t.key}`}
              >
                {t.icon} {t.label}
              </button>
            ))}
          </div>
        </div>

        {activeTab === "overview" && <OverviewTab />}
        {activeTab === "users" && <UsersTab currentUser={user} />}
        {activeTab === "feedback" && <FeedbackTab />}
        {activeTab === "review" && <DecryptionReviewTab />}
      </div>
    </Layout>
  );
}

/* ============================================================
 * OVERVIEW TAB
 * ============================================================ */
const OverviewTab = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/admin/overview`, { credentials: "include" });
        if (res.ok) setData(await res.json());
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <Spinner />;
  if (!data) return <p className="text-sm" style={{ color: WINE }}>Failed to load overview.</p>;

  const stats = [
    { label: "Total Users", value: data.total_users, icon: <Users className="w-4 h-4" style={{ color: WINE }} /> },
    { label: "Active (7d)", value: data.active_7d, icon: <UserIcon className="w-4 h-4 text-emerald-600" /> },
    { label: "Active (30d)", value: data.active_30d, icon: <UserIcon className="w-4 h-4" style={{ color: GOLD_TEXT }} /> },
    { label: "Total Games", value: data.total_games, icon: <Gamepad2 className="w-4 h-4" style={{ color: GOLD_TEXT }} /> },
    { label: "Analyses", value: data.total_analyses, icon: <Brain className="w-4 h-4" style={{ color: WINE }} /> },
    { label: "Community Pool", value: data.community_positions, icon: <BookOpen className="w-4 h-4" style={{ color: GOLD_TEXT }} /> },
    { label: "Feedback Pending", value: data.feedback_pending, icon: <Flag className="w-4 h-4" style={{ color: WINE }} /> },
    { label: "Feedback Total", value: data.feedback_total, icon: <MessageSquareWarning className="w-4 h-4 text-muted-foreground" /> },
  ];

  return (
    <div className="space-y-6" data-testid="admin-overview">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {stats.map((s) => (
          <Card key={s.label}>
            <div className="p-3">
              <div className="flex items-center gap-2 mb-1.5">
                {s.icon}
                <span className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider">{s.label}</span>
              </div>
              <p className="text-xl text-foreground font-light font-heading" data-testid={`stat-${s.label.toLowerCase().replace(/[\s()]/g, '-')}`}>
                {s.value}
              </p>
            </div>
          </Card>
        ))}
      </div>

      {data.recent_users?.length > 0 && (
        <div>
          <SectionLabel>Recent Signups</SectionLabel>
          <div className="space-y-1">
            {data.recent_users.map((u, i) => (
              <div key={i} className="flex items-center justify-between py-2 px-3 rounded-sm bg-white border text-sm" style={{ borderColor: BORDER }}>
                <span className="text-foreground font-light">{u.name || u.email || u.user_id}</span>
                <div className="flex items-center gap-2">
                  <RoleBadge role={u.role} />
                  <span className="text-[10px] text-muted-foreground font-mono">{formatDate(u.created_at)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

/* ============================================================
 * USERS TAB
 * ============================================================ */
const UsersTab = ({ currentUser }) => {
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [selectedUser, setSelectedUser] = useState(null);
  const [detailData, setDetailData] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ name: "", email: "", rating: 1200, role: "user" });
  const [creating, setCreating] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (roleFilter && roleFilter !== "all") params.set("role", roleFilter);
      const res = await fetch(`${API}/admin/users?${params}`, { credentials: "include" });
      if (res.ok) {
        const d = await res.json();
        setUsers(d.users);
        setTotal(d.total);
      }
    } finally {
      setLoading(false);
    }
  }, [search, roleFilter]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const openDetail = async (userId) => {
    setSelectedUser(userId);
    setDetailLoading(true);
    setDetailData(null);
    try {
      const res = await fetch(`${API}/admin/users/${userId}`, { credentials: "include" });
      if (res.ok) setDetailData(await res.json());
    } finally {
      setDetailLoading(false);
    }
  };

  const changeRole = async (userId, newRole) => {
    const res = await fetch(`${API}/admin/users/${userId}/role`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ role: newRole }),
    });
    if (res.ok) {
      fetchUsers();
      if (detailData?.user?.user_id === userId) {
        setDetailData((d) => ({ ...d, user: { ...d.user, role: newRole } }));
      }
    }
  };

  const handleCreate = async () => {
    setCreating(true);
    try {
      const res = await fetch(`${API}/admin/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(createForm),
      });
      if (res.ok) {
        setShowCreate(false);
        setCreateForm({ name: "", email: "", rating: 1200, role: "user" });
        fetchUsers();
      }
    } finally {
      setCreating(false);
    }
  };

  if (selectedUser && detailData) {
    return <UserDetail data={detailData} onBack={() => setSelectedUser(null)} onChangeRole={changeRole} currentUser={currentUser} />;
  }
  if (selectedUser && detailLoading) return <Spinner />;

  return (
    <div className="space-y-4" data-testid="admin-users">
      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            placeholder="Search by name, email..."
            className="w-full pl-9 pr-3 py-2 text-sm bg-white border rounded-sm font-light focus:outline-none focus:ring-1"
            style={{ borderColor: BORDER, "--tw-ring-color": WINE }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            data-testid="user-search"
          />
        </div>
        <select
          className="px-3 py-2 text-sm bg-white border rounded-sm font-light"
          style={{ borderColor: BORDER }}
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          data-testid="role-filter"
        >
          <option value="all">All roles</option>
          <option value="user">User</option>
          <option value="admin">Admin</option>
          <option value="super_admin">Super Admin</option>
        </select>
        {currentUser?.role === "super_admin" && (
          <button
            className="px-3 py-2 text-sm text-white rounded-sm flex items-center gap-1.5 font-light"
            style={{ background: WINE }}
            onClick={() => setShowCreate(true)}
            data-testid="create-user-btn"
          >
            <UserPlus className="w-3.5 h-3.5" /> Create
          </button>
        )}
      </div>

      <p className="text-[10px] text-muted-foreground font-mono">{total} users</p>

      {loading ? <Spinner /> : (
        <div className="space-y-1">
          {users.map((u) => (
            <div
              key={u.user_id}
              className="flex items-center justify-between py-2.5 px-4 rounded-sm bg-white border cursor-pointer transition-colors hover:shadow-sm"
              style={{ borderColor: BORDER }}
              onClick={() => openDetail(u.user_id)}
              data-testid={`user-row-${u.user_id}`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs text-white font-light shrink-0" style={{ background: WINE }}>
                  {(u.name || "?")[0]}
                </div>
                <div className="min-w-0">
                  <p className="text-sm text-foreground font-light truncate">{u.name || u.email}</p>
                  <p className="text-[10px] text-muted-foreground truncate font-mono">{u.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-[10px] text-muted-foreground font-mono">{u.game_count} games</span>
                <RoleBadge role={u.role} />
                <ChevronRight className="w-4 h-4 text-muted-foreground/30" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create User Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center" onClick={() => setShowCreate(false)}>
          <div className="bg-white rounded-sm border p-6 w-full max-w-md space-y-4" style={{ borderColor: BORDER }} onClick={(e) => e.stopPropagation()} data-testid="create-user-dialog">
            <h3 className="text-lg text-foreground font-heading">Create New User</h3>
            <input placeholder="Name" className="w-full px-3 py-2 text-sm border rounded-sm font-light" style={{ borderColor: BORDER }} value={createForm.name} onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))} data-testid="create-name-input" />
            <input placeholder="Email" type="email" className="w-full px-3 py-2 text-sm border rounded-sm font-light" style={{ borderColor: BORDER }} value={createForm.email} onChange={(e) => setCreateForm((f) => ({ ...f, email: e.target.value }))} data-testid="create-email-input" />
            <input placeholder="Rating" type="number" className="w-full px-3 py-2 text-sm border rounded-sm font-light" style={{ borderColor: BORDER }} value={createForm.rating} onChange={(e) => setCreateForm((f) => ({ ...f, rating: parseInt(e.target.value) || 1200 }))} data-testid="create-rating-input" />
            <select className="w-full px-3 py-2 text-sm border rounded-sm font-light" style={{ borderColor: BORDER }} value={createForm.role} onChange={(e) => setCreateForm((f) => ({ ...f, role: e.target.value }))} data-testid="create-role-select">
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
            <button className="w-full py-2 text-sm text-white rounded-sm font-light" style={{ background: WINE, opacity: creating || !createForm.name || !createForm.email ? 0.5 : 1 }} onClick={handleCreate} disabled={creating || !createForm.name || !createForm.email} data-testid="create-user-submit">
              {creating ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Create User"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

/* ============================================================
 * USER DETAIL VIEW — rich drill-down
 * ============================================================ */
const UserDetail = ({ data, onBack, onChangeRole, currentUser }) => {
  const u = data.user;
  const isSuperAdmin = currentUser?.role === "super_admin";

  // Every section is collapsible. Default-open sections: rating, engine1, engine2.
  const [open, setOpen] = useState({
    rating: true,
    games: false,
    engine1: true,
    engine2: true,
    engagement: false,
    openings: false,
    habits: false,
    feedback: false,
    gaps: true,
    activity: false,
  });
  const toggle = (k) => setOpen((s) => ({ ...s, [k]: !s[k] }));

  // Activity timeline is loaded lazily when the user opens that section —
  // it can be heavy for active users.
  const [activity, setActivity] = useState(null);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityFilter, setActivityFilter] = useState("all");
  const [activityDays, setActivityDays] = useState(null); // null = all time

  const loadActivity = useCallback(async (days) => {
    setActivityLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("limit", "200");
      if (days) params.set("days", String(days));
      const res = await fetch(`${API}/admin/users/${u.user_id}/activity?${params}`, {
        credentials: "include",
      });
      if (res.ok) setActivity(await res.json());
    } finally { setActivityLoading(false); }
  }, [u.user_id]);

  // Auto-fetch when activity section is opened the first time
  useEffect(() => {
    if (open.activity && !activity && !activityLoading) {
      loadActivity(activityDays);
    }
  }, [open.activity, activity, activityLoading, loadActivity, activityDays]);

  const rating = data.rating_signals || {};
  const pgn = rating.pgn_inferred || {};
  const perf = rating.performance_rated || {};
  const platform = rating.platform_reported || {};
  const engine1 = data.engine1;
  const engine2 = data.engine2;
  const eng = data.engagement || {};
  const gaps = data.gaps || [];

  return (
    <div className="space-y-4" data-testid="user-detail">
      <button onClick={onBack} className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors" data-testid="back-to-users-btn">
        <ArrowLeft className="w-3 h-3" /> Back to users
      </button>

      {/* Header strip */}
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-full flex items-center justify-center text-lg text-white font-light" style={{ background: WINE }}>
          {(u.name || "?")[0]}
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-lg text-foreground font-heading truncate">{u.name}</h2>
          <p className="text-[10px] text-muted-foreground font-mono truncate">{u.email} · {u.user_id}</p>
        </div>
        <div className="flex items-center gap-2">
          <RoleBadge role={u.role} />
          {isSuperAdmin && u.user_id !== currentUser.user_id && (
            <select
              className="px-2 py-1 text-xs border rounded-sm font-light"
              style={{ borderColor: BORDER }}
              value={u.role || "user"}
              onChange={(e) => onChangeRole(u.user_id, e.target.value)}
              data-testid="change-role-select"
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
              <option value="super_admin">Super Admin</option>
            </select>
          )}
        </div>
      </div>

      {/* Quick-glance chips */}
      <div className="flex flex-wrap items-center gap-2">
        <Chip label="Games" value={data.game_count} />
        <Chip label="Analyzed" value={data.analysis_count} />
        <Chip label="PGN rating" value={pgn.rating || "—"} />
        <Chip label="Band" value={bandOf(perf.best || pgn.rating || 0)} />
        <Chip label="Focus" value={engine1?.current_focus || "—"} highlight />
        <Chip label="Sessions" value={eng.coach_sessions || 0} />
        <Chip label="Joined" value={formatDate(u.created_at)} />
      </div>

      {/* Gaps detected */}
      {gaps.length > 0 && (
        <Section title={`Gaps detected (${gaps.length})`} open={open.gaps} onToggle={() => toggle("gaps")} color="#92400e">
          <ul className="text-xs space-y-1.5">
            {gaps.map((g, i) => (
              <li key={i} className="text-foreground font-light flex gap-2">
                <span style={{ color: "#92400e" }}>!</span>
                <span>{g}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* Rating — three sources */}
      <Section title="Rating — what ChessGuru sees" open={open.rating} onToggle={() => toggle("rating")}>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <RatingCard title="Platform-reported" subtitle="self-declared">
            <KV label="Chess.com" value={platform.chesscom || "—"} />
            <KV label="Lichess" value={platform.lichess || "—"} />
          </RatingCard>
          <RatingCard title="PGN-inferred" subtitle="from game headers" strong>
            <KV label="Current" value={pgn.rating || "—"} />
            <KV label="Avg" value={pgn.avg_rating || "—"} />
            <KV label="High / Low" value={`${pgn.highest_rating || "—"} / ${pgn.lowest_rating || "—"}`} />
            <KV label="Trend" value={pgn.rating_trend || "—"} />
            <KV label="Games used" value={pgn.games_analyzed || 0} />
          </RatingCard>
          <RatingCard title="Performance-rated" subtitle="from Stockfish">
            <KV label="Best" value={perf.best || "—"} />
            <KV label="Worst" value={perf.worst || "—"} />
            <KV label="Games" value={perf.games_played || 0} />
            <KV label="Avg accuracy" value={perf.avg_accuracy ? `${perf.avg_accuracy}%` : "—"} />
            <KV label="Improvement" value={perf.improvement_rate ?? "—"} />
          </RatingCard>
        </div>
      </Section>

      {/* Engine 1 */}
      {engine1 && (
        <Section title="Engine 1 — Fix Your Mess" open={open.engine1} onToggle={() => toggle("engine1")}>
          <Card className="mb-3">
            <div className="p-3 text-xs space-y-1">
              <KV label="Current focus" value={engine1.current_focus || "(none set)"} strong />
              {engine1.suggested_next?.length > 0 && (
                <KV label="Suggested next" value={engine1.suggested_next.join(", ")} />
              )}
            </div>
          </Card>

          {engine1.top_weaknesses?.length > 0 && (
            <>
              <p className="text-[10px] text-muted-foreground font-mono mb-1">Top weaknesses (by detection count)</p>
              <div className="space-y-1 mb-3">
                {engine1.top_weaknesses.map((w, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 px-3 rounded-sm bg-white border text-xs" style={{ borderColor: BORDER }}>
                    <span className="text-foreground font-light truncate">{w.name || w.habit_id}</span>
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-muted-foreground">{w.detection_count}×</span>
                      <span className="text-[10px] font-mono" style={{ color: w.improving ? "#16a34a" : "#888" }}>
                        {w.improving ? "↗ improving" : "· active"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {engine1.recent_prescriptions?.length > 0 && (
            <>
              <p className="text-[10px] text-muted-foreground font-mono mb-1">Last 5 prescriptions</p>
              <div className="space-y-1">
                {engine1.recent_prescriptions.map((p, i) => (
                  <div key={i} className="py-1.5 px-3 rounded-sm bg-white border text-xs" style={{ borderColor: BORDER }}>
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-foreground">{p.coach_prescription}</span>
                      <span className="text-[10px] text-muted-foreground font-mono">{formatDate(p.created_at)}</span>
                    </div>
                    {p.prescription_reason && (
                      <p className="text-[11px] text-muted-foreground font-light mt-0.5 truncate">{p.prescription_reason}</p>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </Section>
      )}

      {/* Engine 2 */}
      {engine2 && (
        <Section title="Engine 2 — Build New Skills" open={open.engine2} onToggle={() => toggle("engine2")}>
          {engine2.next_pick && (
            <Card className="mb-3">
              <div className="p-3 text-xs">
                <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider mb-1">Next skill</p>
                <p className="text-sm text-foreground font-heading">{engine2.next_pick.label}</p>
                <p className="text-[11px] text-muted-foreground font-light mt-0.5">{engine2.next_pick.reason}</p>
              </div>
            </Card>
          )}

          {engine2.skills?.length > 0 ? (
            <div className="space-y-1 mb-3">
              {engine2.skills.map((s, i) => (
                <div key={i} className="flex items-center justify-between py-2 px-3 rounded-sm bg-white border text-xs" style={{ borderColor: BORDER }}>
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-foreground font-light truncate">{s.skill_id}</span>
                    {s.learned && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded-sm font-mono" style={{ color: "#16a34a", background: "rgba(22,163,74,0.08)" }}>
                        Learned
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="font-mono text-muted-foreground">
                      {s.correct}/{s.seen}
                    </span>
                    <div className="flex gap-0.5">
                      {s.outcomes.map((o, j) => (
                        <span key={j} className="text-[10px] font-mono" style={{
                          color: o === "correct" ? "#16a34a" : o === "wrong" ? "#dc2626" : "#999"
                        }}>
                          {o === "correct" ? "●" : o === "wrong" ? "●" : "○"}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground font-light mb-3">
              No skill attempts recorded. Run the backfill script.
            </p>
          )}

          <LearnedInventory data={engine2} />
        </Section>
      )}

      {/* Games */}
      <Section
        title={`Games (${data.analysis_count} analyzed / ${data.game_count} imported)`}
        open={open.games}
        onToggle={() => toggle("games")}
      >
        {Object.keys(data.games_by_platform || {}).length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {Object.entries(data.games_by_platform).map(([plat, n]) => (
              <span key={plat} className="text-[10px] px-2 py-1 rounded-sm font-mono" style={{ color: WINE, background: "rgba(114,47,55,0.06)" }}>
                {plat}: {n}
              </span>
            ))}
          </div>
        )}
        {Object.keys(data.termination_mix || {}).length > 0 && (
          <>
            <p className="text-[10px] text-muted-foreground font-mono mb-1">Termination mix</p>
            <div className="flex flex-wrap gap-2 mb-3">
              {Object.entries(data.termination_mix).map(([term, n]) => (
                <span key={term} className="text-[10px] px-2 py-1 rounded-sm font-mono bg-white border" style={{ borderColor: BORDER }}>
                  {term}: {n}
                </span>
              ))}
            </div>
          </>
        )}

        {data.recent_games?.length > 0 && (
          <>
            <p className="text-[10px] text-muted-foreground font-mono mb-1">Recent games — click to review</p>
            <div className="space-y-1">
              {data.recent_games.map((g) => {
                const won = (g.result?.includes("1-0") && g.user_color === "white")
                         || (g.result?.includes("0-1") && g.user_color === "black");
                return (
                  <a
                    key={g.game_id}
                    href={`/game/${g.game_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between py-2 px-3 rounded-sm bg-white border text-xs hover:shadow-sm transition-shadow cursor-pointer"
                    style={{ borderColor: BORDER }}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-foreground font-light truncate">{g.opening || "Unknown"}</span>
                      {g.termination && (
                        <span className="text-[9px] text-muted-foreground font-mono">· {g.termination}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[9px] px-1.5 py-0.5 rounded-sm border font-mono" style={{ borderColor: BORDER }}>
                        {g.user_color}
                      </span>
                      <span className="font-mono" style={{ color: won ? "#16a34a" : WINE }}>
                        {g.result || "—"}
                      </span>
                      <ChevronRight className="w-3 h-3 text-muted-foreground/40" />
                    </div>
                  </a>
                );
              })}
            </div>
          </>
        )}
      </Section>

      {/* Engagement */}
      <Section title="Engagement" open={open.engagement} onToggle={() => toggle("engagement")}>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <MiniStat label="Sessions" value={eng.coach_sessions || 0} sub={`${eng.coach_sessions_completed || 0} completed`} />
          <MiniStat label="Messages" value={eng.coach_messages || 0} />
          <MiniStat label="Puzzles" value={eng.puzzle_attempts || 0} sub={`${eng.puzzle_solved || 0} solved`} />
          <MiniStat label="Notifications" value={eng.notifications_sent || 0} />
        </div>
        {eng.last_active && (
          <p className="text-[10px] text-muted-foreground font-mono mt-3">
            Last active: {formatDate(eng.last_active)}
          </p>
        )}
      </Section>

      {/* Openings */}
      {data.opening_progress?.length > 0 && (
        <Section title="Opening progress" open={open.openings} onToggle={() => toggle("openings")}>
          <div className="space-y-1">
            {data.opening_progress.map((op, i) => (
              <div key={i} className="flex items-center justify-between py-2 px-3 rounded-sm bg-white border text-xs" style={{ borderColor: BORDER }}>
                <span className="text-foreground font-light">{op.opening_key?.replace(/_/g, " ") || "Unknown"}</span>
                <span className="text-muted-foreground font-mono">Mastery: {op.mastery_level || 0}%</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Habits (raw) */}
      {data.habits && (
        <Section title="Player habits (raw)" open={open.habits} onToggle={() => toggle("habits")}>
          <Card>
            <div className="p-3">
              <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
                {Object.entries(data.habits)
                  .filter(([k]) => !["user_id", "_id", "updated_at"].includes(k))
                  .slice(0, 12)
                  .map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-muted-foreground font-light">{k.replace(/_/g, " ")}</span>
                      <span className="font-mono text-foreground">{typeof v === "number" ? v.toFixed?.(2) ?? v : String(v).slice(0, 30)}</span>
                    </div>
                  ))}
              </div>
            </div>
          </Card>
        </Section>
      )}

      {/* Activity timeline */}
      <Section
        title={`Activity timeline${activity ? ` (${activity.total_returned})` : ""}`}
        open={open.activity}
        onToggle={() => toggle("activity")}
      >
        <div className="flex items-center gap-2 flex-wrap mb-3">
          {[
            { label: "All time", days: null },
            { label: "7d", days: 7 },
            { label: "30d", days: 30 },
            { label: "90d", days: 90 },
          ].map((r) => (
            <button
              key={r.label}
              onClick={() => {
                setActivityDays(r.days);
                setActivity(null);
                loadActivity(r.days);
              }}
              className="px-2 py-1 text-[10px] rounded-sm border font-mono transition"
              style={{
                borderColor: BORDER,
                background: activityDays === r.days ? "rgba(114,47,55,0.08)" : "white",
                color: activityDays === r.days ? WINE : "#555",
              }}
            >
              {r.label}
            </button>
          ))}
          {activity?.counts && (
            <div className="flex items-center gap-1.5 ml-auto">
              {Object.entries(activity.counts).map(([k, v]) => (
                <span
                  key={k}
                  onClick={() => setActivityFilter(activityFilter === k ? "all" : k)}
                  className="text-[10px] px-1.5 py-0.5 rounded-sm cursor-pointer font-mono transition"
                  style={{
                    background: activityFilter === k ? "rgba(114,47,55,0.08)" : "rgba(0,0,0,0.04)",
                    color: activityFilter === k ? WINE : "#555",
                  }}
                >
                  {k} · {v}
                </span>
              ))}
              {activityFilter !== "all" && (
                <button
                  onClick={() => setActivityFilter("all")}
                  className="text-[10px] text-muted-foreground hover:text-foreground"
                >
                  clear
                </button>
              )}
            </div>
          )}
        </div>

        {activityLoading ? (
          <div className="flex justify-center py-6">
            <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
          </div>
        ) : !activity ? (
          <p className="text-xs text-muted-foreground font-light">Loading activity…</p>
        ) : activity.events.length === 0 ? (
          <p className="text-xs text-muted-foreground font-light">No activity in this window.</p>
        ) : (
          <div className="space-y-1">
            {activity.events
              .filter((e) => activityFilter === "all" || e.type === activityFilter)
              .map((e, i) => (
                <ActivityRow key={i} event={e} />
              ))}
          </div>
        )}
      </Section>

      {/* User feedback */}
      {data.feedback?.length > 0 && (
        <Section title={`User-submitted feedback (${data.feedback.length})`} open={open.feedback} onToggle={() => toggle("feedback")}>
          <div className="space-y-1">
            {data.feedback.map((fb, i) => (
              <div key={i} className="py-2 px-3 rounded-sm bg-white border text-xs" style={{ borderColor: BORDER }}>
                <p className="text-foreground font-light">{fb.comment || fb.message || "(no comment)"}</p>
                <p className="text-[10px] text-muted-foreground font-mono mt-1">{formatDate(fb.created_at)}</p>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
};


/* ─── sub-components for UserDetail ─── */

const Section = ({ title, open, onToggle, color, children }) => (
  <div className="space-y-2">
    <button
      onClick={onToggle}
      className="flex items-center justify-between w-full text-left py-2 border-b transition-colors hover:opacity-80"
      style={{ borderColor: BORDER }}
    >
      <span className="text-[10px] tracking-[0.2em] uppercase font-mono" style={{ color: color || GOLD_TEXT }}>
        {title}
      </span>
      <ChevronRight
        className="w-4 h-4 text-muted-foreground/50 transition-transform"
        style={{ transform: open ? "rotate(90deg)" : "rotate(0deg)" }}
      />
    </button>
    {open && <div className="pt-1">{children}</div>}
  </div>
);

const Chip = ({ label, value, highlight }) => (
  <div
    className="flex items-center gap-1.5 px-2 py-1 rounded-sm border text-[10px] font-mono"
    style={{
      borderColor: highlight ? WINE : BORDER,
      background: highlight ? "rgba(114,47,55,0.04)" : "white",
    }}
  >
    <span className="text-muted-foreground">{label}:</span>
    <span className="text-foreground font-medium">{value}</span>
  </div>
);

const RatingCard = ({ title, subtitle, strong, children }) => (
  <div
    className="bg-white border rounded-sm p-3"
    style={{
      borderColor: strong ? WINE : BORDER,
      boxShadow: strong ? "0 0 0 1px rgba(114,47,55,0.1)" : undefined,
    }}
  >
    <p className="text-[10px] tracking-[0.15em] uppercase font-mono mb-0.5" style={{ color: strong ? WINE : GOLD_TEXT }}>
      {title}
    </p>
    <p className="text-[9px] text-muted-foreground font-light mb-2">{subtitle}</p>
    <div className="space-y-0.5">{children}</div>
  </div>
);

const KV = ({ label, value, strong }) => (
  <div className="flex justify-between gap-2">
    <span className="text-muted-foreground font-light">{label}</span>
    <span className={`font-mono text-foreground ${strong ? "font-medium" : ""}`}>{value}</span>
  </div>
);

const MiniStat = ({ label, value, sub }) => (
  <div className="bg-white border rounded-sm p-2.5" style={{ borderColor: BORDER }}>
    <p className="text-[9px] text-muted-foreground font-mono uppercase tracking-wider">{label}</p>
    <p className="text-base text-foreground font-light font-heading">{value}</p>
    {sub && <p className="text-[9px] text-muted-foreground font-mono mt-0.5">{sub}</p>}
  </div>
);

const LearnedInventory = ({ data }) => {
  const buckets = [
    ["Concepts", data.concepts_mastered || []],
    ["Openings", data.openings_learned || []],
    ["Traps", data.traps_learned || []],
    ["Endgames", data.endgames_learned || []],
  ];
  const hasAny = buckets.some(([, arr]) => arr.length > 0);
  if (!hasAny) return <p className="text-[11px] text-muted-foreground font-light">Nothing learned yet.</p>;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {buckets.map(([label, items]) => (
        <div key={label} className="text-xs">
          <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider mb-1">{label}</p>
          {items.length === 0 ? (
            <p className="text-[11px] text-muted-foreground font-light">—</p>
          ) : (
            <div className="flex flex-wrap gap-1">
              {items.map((x, i) => (
                <span key={i} className="text-[10px] px-1.5 py-0.5 rounded-sm font-mono" style={{ color: "#16a34a", background: "rgba(22,163,74,0.06)" }}>
                  {x}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

function bandOf(rating) {
  if (!rating) return "—";
  if (rating < 1000) return "beginner low";
  if (rating < 1400) return "beginner high";
  if (rating < 1800) return "intermediate";
  return "advanced";
}


const EVENT_TYPE_STYLE = {
  game:          { color: "#2563eb", label: "game" },
  analysis:      { color: "#6b7280", label: "analysis" },
  coach:         { color: "#b45309", label: "coach" },
  prescription:  { color: "#722F37", label: "prescription" },
  puzzle:        { color: "#16a34a", label: "puzzle" },
  opening:       { color: "#7c3aed", label: "opening" },
  notification:  { color: "#999", label: "notif" },
};

const formatRelTs = (iso) => {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    const diff = Date.now() - d.getTime();
    const s = Math.floor(diff / 1000);
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    const days = Math.floor(s / 86400);
    if (days < 7) return `${days}d ago`;
    if (days < 30) return `${Math.floor(days / 7)}w ago`;
    return `${Math.floor(days / 30)}mo ago`;
  } catch { return iso; }
};

const formatAbsTs = (iso) => {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      year: "2-digit", month: "short", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
};

const ActivityRow = ({ event }) => {
  const style = EVENT_TYPE_STYLE[event.type] || { color: "#666", label: event.type };
  const clickable = event.game_id || event.session_id;
  const href = event.game_id ? `/game/${event.game_id}`
             : event.session_id ? `/game/${event.session_id}`
             : null;

  const content = (
    <div
      className="flex items-start gap-3 py-2 px-3 rounded-sm bg-white border text-xs transition-colors"
      style={{ borderColor: BORDER, cursor: clickable ? "pointer" : "default" }}
    >
      <div className="shrink-0 flex flex-col items-center pt-0.5 w-[72px]">
        <span
          className="text-[9px] px-1.5 py-0.5 rounded-sm font-mono"
          style={{ color: style.color, background: `${style.color}15` }}
        >
          {style.label}
        </span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-foreground font-light">{event.summary}</p>
        {event.detail && (
          <p className="text-[10px] text-muted-foreground/70 font-light mt-0.5">{event.detail}</p>
        )}
      </div>
      <div className="shrink-0 text-right">
        <p className="text-[10px] text-muted-foreground font-mono whitespace-nowrap">
          {formatRelTs(event.ts_iso)}
        </p>
        <p className="text-[9px] text-muted-foreground/50 font-mono whitespace-nowrap">
          {formatAbsTs(event.ts_iso)}
        </p>
      </div>
    </div>
  );

  if (href) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="block hover:shadow-sm">
        {content}
      </a>
    );
  }
  return content;
};

/* ============================================================
 * FEEDBACK TAB
 * ============================================================ */
const FeedbackTab = () => {
  const [feedback, setFeedback] = useState([]);
  const [total, setTotal] = useState(0);
  const [pending, setPending] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [expandedId, setExpandedId] = useState(null);
  const [adminNotes, setAdminNotes] = useState("");

  const fetchFeedback = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter && statusFilter !== "all") params.set("status", statusFilter);
      if (sourceFilter && sourceFilter !== "all") params.set("source", sourceFilter);
      const res = await fetch(`${API}/admin/feedback?${params}`, { credentials: "include" });
      if (res.ok) {
        const d = await res.json();
        setFeedback(d.feedback);
        setTotal(d.total);
        setPending(d.pending);
      }
    } finally {
      setLoading(false);
    }
  }, [statusFilter, sourceFilter]);

  useEffect(() => { fetchFeedback(); }, [fetchFeedback]);

  const [exportJson, setExportJson] = useState(null);
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter && statusFilter !== "all") params.set("status", statusFilter);
      if (sourceFilter && sourceFilter !== "all") params.set("source", sourceFilter);
      const res = await fetch(`${API}/admin/feedback/export?${params}`, { credentials: "include" });
      if (!res.ok) {
        alert(`Export failed: ${(await res.json().catch(() => ({}))).detail || res.statusText}`);
        return;
      }
      const meta = await res.json();
      // Fetch the actual file
      const fileRes = await fetch(`${API}${meta.file_url}`, { credentials: "include" });
      if (!fileRes.ok) { alert("Failed to fetch export file"); return; }
      const text = await fileRes.text();
      setExportJson(text);
      setCopied(false);
    } catch (e) {
      alert(`Export error: ${e.message}`);
    } finally {
      setExporting(false);
    }
  };

  const handleCopy = async () => {
    if (!exportJson) return;
    await navigator.clipboard.writeText(exportJson);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const updateStatus = async (feedbackId, status) => {
    const res = await fetch(`${API}/admin/feedback/${feedbackId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ status, admin_notes: adminNotes || undefined }),
    });
    if (res.ok) {
      setAdminNotes("");
      fetchFeedback();
    }
  };

  const statusStyle = {
    pending: { color: "#92400e", bg: "rgba(245,158,11,0.08)" },
    acknowledged: { color: GOLD_TEXT, bg: GOLD_BG },
    valid: { color: WINE, bg: "rgba(114,47,55,0.06)" },
    dismissed: { color: "#999", bg: "rgba(0,0,0,0.03)" },
  };

  const statusIcons = {
    pending: <Clock className="w-3 h-3" />,
    acknowledged: <Eye className="w-3 h-3" />,
    valid: <Flag className="w-3 h-3" />,
    dismissed: <X className="w-3 h-3" />,
  };

  return (
    <div className="space-y-4" data-testid="admin-feedback">
      {/* Filters */}
      <div className="flex items-center gap-3">
        <select className="px-3 py-2 text-sm bg-white border rounded-sm font-light" style={{ borderColor: BORDER }} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} data-testid="feedback-status-filter">
          <option value="all">All status</option>
          <option value="pending">Pending</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="valid">Valid</option>
          <option value="dismissed">Dismissed</option>
        </select>
        <select className="px-3 py-2 text-sm bg-white border rounded-sm font-light" style={{ borderColor: BORDER }} value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} data-testid="feedback-source-filter">
          <option value="all">All sources</option>
          <option value="lab">Lab</option>
          <option value="coach">Coach</option>
        </select>
        <span className="text-[10px] text-muted-foreground ml-auto font-mono">
          {pending} pending · {total} total
        </span>
        <button
          className="px-3 py-2 text-sm text-white rounded-sm flex items-center gap-1.5 font-light disabled:opacity-50"
          style={{ background: WINE }}
          onClick={handleExport}
          disabled={total === 0 || exporting}
          data-testid="export-feedback-btn"
        >
          {exporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
          Export JSON
        </button>
        {exportJson && (
          <button
            className="px-3 py-2 text-sm rounded-sm flex items-center gap-1.5 font-light border"
            style={{ color: copied ? "#16a34a" : WINE, borderColor: copied ? "#16a34a" : WINE }}
            onClick={handleCopy}
            data-testid="copy-feedback-btn"
          >
            {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? "Copied!" : "Copy JSON"}
          </button>
        )}
      </div>

      {/* Export JSON Preview */}
      {exportJson && (
        <Card data-testid="export-preview">
          <div className="p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] tracking-[0.15em] uppercase font-mono" style={{ color: GOLD_TEXT }}>Export Preview</span>
              <button className="text-[10px] text-muted-foreground hover:text-foreground" onClick={() => setExportJson(null)}>
                <X className="w-3 h-3" />
              </button>
            </div>
            <pre className="text-[11px] font-mono bg-zinc-50 border rounded-sm p-3 max-h-64 overflow-auto whitespace-pre-wrap" style={{ borderColor: BORDER }} data-testid="export-json-preview">
              {exportJson}
            </pre>
          </div>
        </Card>
      )}

      {loading ? <Spinner /> : feedback.length === 0 ? (
        <div className="text-center py-16" data-testid="feedback-empty">
          <MessageSquareWarning className="w-8 h-8 mx-auto mb-3 text-muted-foreground/30" />
          <p className="text-sm text-muted-foreground font-light">No feedback yet.</p>
          <p className="text-xs text-muted-foreground/60 mt-1">Users can flag moves in Lab and Coach when coaching seems wrong.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {feedback.map((fb) => {
            const st = statusStyle[fb.status] || statusStyle.pending;
            const isExpanded = expandedId === fb.feedback_id;
            return (
              <Card
                key={fb.feedback_id}
                className={`cursor-pointer transition-shadow ${isExpanded ? "shadow-sm" : ""}`}
                onClick={() => setExpandedId(isExpanded ? null : fb.feedback_id)}
                data-testid={`feedback-item-${fb.feedback_id}`}
              >
                <div className="p-3">
                  {/* Header row */}
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-[9px] px-1.5 py-0.5 rounded-sm flex items-center gap-1 font-mono uppercase" style={{ color: st.color, background: st.bg }}>
                        {statusIcons[fb.status]} {fb.status}
                      </span>
                      <span className="text-[9px] px-1.5 py-0.5 rounded-sm border font-mono" style={{ borderColor: BORDER }}>{fb.source}</span>
                      <span className="text-sm text-foreground font-light truncate">{fb.user_name || fb.user_id}</span>
                      {fb.user_rating && <span className="text-[10px] text-muted-foreground font-mono">({fb.user_rating})</span>}
                    </div>
                    <span className="text-[10px] text-muted-foreground shrink-0 font-mono">{formatDate(fb.created_at)}</span>
                  </div>

                  <p className="text-sm text-foreground/80 mt-2 font-light line-clamp-2">{fb.user_note}</p>

                  {/* Expanded details */}
                  {isExpanded && (
                    <div className="mt-3 space-y-2 border-t pt-3" style={{ borderColor: BORDER }} onClick={(e) => e.stopPropagation()}>
                      {fb.fen && (
                        <div className="text-xs">
                          <span className="text-muted-foreground">FEN: </span>
                          <code className="px-1.5 py-0.5 rounded-sm text-[10px] font-mono" style={{ background: "rgba(0,0,0,0.03)" }}>{fb.fen}</code>
                        </div>
                      )}
                      {fb.move_san && (
                        <div className="text-xs">
                          <span className="text-muted-foreground">Move: </span>
                          <span className="font-mono text-foreground">{fb.move_san}</span>
                          {fb.move_number && <span className="text-muted-foreground"> (move {fb.move_number})</span>}
                        </div>
                      )}
                      {fb.coaching_text && (
                        <div className="text-xs p-2 rounded-sm font-light" style={{ background: "rgba(0,0,0,0.02)" }}>
                          <span className="text-muted-foreground">Coaching said: </span>
                          <span className="text-foreground/80">{fb.coaching_text}</span>
                        </div>
                      )}

                      {/* Diagnostics */}
                      {fb.diagnostics && Object.values(fb.diagnostics).some(v => v != null) && (
                        <div className="text-[10px] p-2.5 rounded-sm border space-y-1" style={{ borderColor: BORDER, background: "rgba(0,0,0,0.01)" }}>
                          <span className="text-[9px] tracking-[0.15em] uppercase font-mono" style={{ color: GOLD_TEXT }}>Diagnostics</span>
                          <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-1">
                            {fb.diagnostics.severity && <div><span className="text-muted-foreground">Severity:</span> <span className="font-mono" style={{ color: fb.diagnostics.severity === 'blunder' ? WINE : fb.diagnostics.severity === 'mistake' ? '#92400e' : GOLD_TEXT }}>{fb.diagnostics.severity}</span></div>}
                            {fb.diagnostics.cp_loss != null && <div><span className="text-muted-foreground">CP Loss:</span> <span className="font-mono">{fb.diagnostics.cp_loss}</span></div>}
                            {fb.diagnostics.best_move && <div><span className="text-muted-foreground">Best Move:</span> <span className="font-mono text-emerald-600">{fb.diagnostics.best_move}</span></div>}
                            {fb.diagnostics.eval_before != null && <div><span className="text-muted-foreground">Eval Before:</span> <span className="font-mono">{fb.diagnostics.eval_before}</span></div>}
                            {fb.diagnostics.eval_after != null && <div><span className="text-muted-foreground">Eval After:</span> <span className="font-mono">{fb.diagnostics.eval_after}</span></div>}
                            {fb.diagnostics.phase && <div><span className="text-muted-foreground">Phase:</span> <span className="font-mono">{fb.diagnostics.phase}</span></div>}
                            {fb.diagnostics.component && <div><span className="text-muted-foreground">Component:</span> <span className="font-mono" style={{ color: GOLD_TEXT }}>{fb.diagnostics.component}</span></div>}
                            {fb.diagnostics.concept_id && <div><span className="text-muted-foreground">Concept:</span> <span className="font-mono">{fb.diagnostics.concept_id}</span></div>}
                          </div>
                          {fb.diagnostics.goal && <div className="mt-1"><span className="text-muted-foreground">Goal:</span> <span>{fb.diagnostics.goal}</span></div>}
                          {fb.diagnostics.consequence && <div><span className="text-muted-foreground">Consequence:</span> <span>{fb.diagnostics.consequence}</span></div>}
                          {fb.diagnostics.better_approach && <div><span className="text-muted-foreground">Better Approach:</span> <span>{fb.diagnostics.better_approach}</span></div>}
                          {fb.diagnostics.your_plan_now && <div><span className="text-muted-foreground">Your Plan Now:</span> <span>{fb.diagnostics.your_plan_now}</span></div>}
                        </div>
                      )}

                      {fb.admin_notes && (
                        <div className="text-xs p-2 rounded-sm border font-light" style={{ borderColor: BORDER }}>
                          <span className="text-muted-foreground">Admin notes: </span>
                          <span>{fb.admin_notes}</span>
                        </div>
                      )}

                      {/* Action buttons */}
                      <div className="flex items-center gap-2 pt-1">
                        <input
                          placeholder="Admin notes (optional)..."
                          className="flex-1 px-2 py-1.5 text-xs border rounded-sm font-light"
                          style={{ borderColor: BORDER }}
                          value={adminNotes}
                          onChange={(e) => setAdminNotes(e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                          data-testid="admin-notes-input"
                        />
                        <ActionBtn color={GOLD_TEXT} bg={GOLD_BG} icon={<Eye className="w-3 h-3" />} label="Ack" onClick={() => updateStatus(fb.feedback_id, "acknowledged")} testId="btn-acknowledge" />
                        <ActionBtn color={WINE} bg="rgba(114,47,55,0.06)" icon={<Flag className="w-3 h-3" />} label="Valid" onClick={() => updateStatus(fb.feedback_id, "valid")} testId="btn-valid" />
                        <ActionBtn color="#999" bg="rgba(0,0,0,0.03)" icon={<X className="w-3 h-3" />} label="Dismiss" onClick={() => updateStatus(fb.feedback_id, "dismissed")} testId="btn-dismiss" />
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};

/* ============================================================
 * SHARED COMPONENTS
 * ============================================================ */
const SectionLabel = ({ children }) => (
  <p className="text-[10px] tracking-[0.2em] uppercase mb-2 font-mono" style={{ color: GOLD_TEXT }}>
    {children}
  </p>
);

const Card = ({ children, className = "", ...props }) => (
  <div className={`bg-white border rounded-sm ${className}`} style={{ borderColor: BORDER }} {...props}>
    {children}
  </div>
);

const RoleBadge = ({ role }) => {
  const config = {
    super_admin: { icon: <ShieldCheck className="w-3 h-3" />, color: WINE, bg: "rgba(114,47,55,0.06)", label: "Super Admin" },
    admin: { icon: <Shield className="w-3 h-3" />, color: GOLD_TEXT, bg: GOLD_BG, label: "Admin" },
    user: { icon: <UserIcon className="w-3 h-3" />, color: "#888", bg: "rgba(0,0,0,0.03)", label: "User" },
  };
  const c = config[role] || config.user;
  return (
    <span className="text-[9px] px-1.5 py-0.5 rounded-sm flex items-center gap-1 font-mono" style={{ color: c.color, background: c.bg }}>
      {c.icon} {c.label}
    </span>
  );
};

const ActionBtn = ({ color, bg, icon, label, onClick, testId }) => (
  <button
    className="px-2 py-1.5 text-[10px] rounded-sm flex items-center gap-1 font-mono transition-opacity hover:opacity-80"
    style={{ color, background: bg }}
    onClick={onClick}
    data-testid={testId}
  >
    {icon} {label}
  </button>
);

const Spinner = () => (
  <div className="flex items-center justify-center py-12">
    <div className="w-5 h-5 border border-border border-t-foreground/50 rounded-full animate-spin" />
  </div>
);

const formatDate = (dateStr) => {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "—";
  }
};


/* ============================================================
 * DECRYPTION REVIEW TAB
 * Auto-flagged commentaries (confidence < 0.8). Coach reviews
 * each, writes an override, save logs to coach_overrides for
 * offline improvement work — does NOT patch the live moment.
 * ============================================================ */
function DecryptionReviewTab() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [overrideText, setOverrideText] = useState("");
  const [coachNote, setCoachNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [includeOverridden, setIncludeOverridden] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await API.get("/admin/decryption-review", {
        params: { limit: 100, include_overridden: includeOverridden },
      });
      setItems(res.data?.items || []);
      setTotal(res.data?.total || 0);
    } catch (e) {
      console.error("decryption-review load failed", e);
      setItems([]);
    }
    setLoading(false);
  }, [includeOverridden]);

  useEffect(() => { load(); }, [load]);

  const onSelect = (row) => {
    setSelected(row);
    setOverrideText(row?.override?.text || "");
    setCoachNote("");
    setSavedFlash(false);
  };

  const onSave = async () => {
    if (!selected || !overrideText.trim()) return;
    setSaving(true);
    try {
      await API.post("/admin/decryption-review/override", {
        game_id: selected.game_id,
        move_number: selected.move_number,
        move_san: selected.move_san,
        override_text: overrideText.trim(),
        coach_note: coachNote.trim() || null,
      });
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 1800);
      await load();
    } catch (e) {
      console.error("override save failed", e);
      alert("Save failed — check console.");
    }
    setSaving(false);
  };

  if (loading) return <Spinner />;

  if (selected) {
    return (
      <DecryptionReviewDetail
        row={selected}
        overrideText={overrideText}
        setOverrideText={setOverrideText}
        coachNote={coachNote}
        setCoachNote={setCoachNote}
        saving={saving}
        savedFlash={savedFlash}
        onSave={onSave}
        onBack={() => setSelected(null)}
      />
    );
  }

  return (
    <div className="space-y-4" data-testid="decryption-review-tab">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-muted-foreground">
            {items.length} of {total} flagged moments (confidence &lt; 0.8)
          </p>
        </div>
        <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
          <input
            type="checkbox"
            checked={includeOverridden}
            onChange={(e) => setIncludeOverridden(e.target.checked)}
          />
          Show overridden
        </label>
      </div>

      {items.length === 0 ? (
        <div className="text-center py-12 text-sm text-muted-foreground">
          {includeOverridden
            ? "No flagged moments."
            : "Queue is clear. ✨"}
        </div>
      ) : (
        <div className="border rounded" style={{ borderColor: BORDER }}>
          {items.map((row, i) => (
            <button
              key={`${row.game_id}-${row.move_number}-${row.move_san}`}
              onClick={() => onSelect(row)}
              className="w-full text-left px-3 py-2.5 flex items-center gap-3 hover:bg-muted/50 transition"
              style={{
                borderBottom: i < items.length - 1 ? `1px solid ${BORDER}` : "none",
              }}
              data-testid={`review-row-${i}`}
            >
              <div className="w-12 text-center">
                <div className="text-base font-medium" style={{ color: WINE }}>
                  {(row.confidence ?? 0).toFixed(2)}
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-mono">M{row.move_number} {row.move_san}</span>
                  <span className="text-xs text-muted-foreground">
                    cp_loss {row.cp_loss}
                  </span>
                  <span
                    className="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded"
                    style={{ background: GOLD_BG, color: GOLD_TEXT }}
                  >
                    {(row.source || "").replace("template:", "")}
                  </span>
                  {row.override && (
                    <span className="text-[10px] text-green-700">✓ overridden</span>
                  )}
                </div>
                <div className="text-xs text-muted-foreground truncate mt-0.5">
                  {row.text}
                </div>
                <div className="text-[10px] text-muted-foreground/70 mt-0.5 font-mono">
                  game {row.game_id?.slice(0, 8)}…
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-muted-foreground" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}


function DecryptionReviewDetail({
  row, overrideText, setOverrideText, coachNote, setCoachNote,
  saving, savedFlash, onSave, onBack,
}) {
  const bd = row.confidence_breakdown || {};
  return (
    <div className="space-y-4" data-testid="decryption-review-detail">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Back to queue
      </button>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Board */}
        <div className="space-y-2">
          <div className="text-xs text-muted-foreground">
            Position before <span className="font-mono">{row.move_san}</span>
          </div>
          <div style={{ maxWidth: 360 }}>
            <Chessboard
              position={row.fen_before}
              arePiecesDraggable={false}
              boardOrientation={
                (row.fen_before || "").split(" ")[1] === "b" ? "white" : "black"
              }
            />
          </div>
          <div className="text-[10px] text-muted-foreground/70 break-all font-mono">
            {row.fen_before}
          </div>
        </div>

        {/* Facts */}
        <div className="space-y-2 text-sm">
          <FactRow label="Game" value={row.game_id} mono />
          <FactRow label="User" value={row.user_id} mono />
          <FactRow label="Move" value={`#${row.move_number}  ${row.move_san}`} mono />
          <FactRow label="Best move" value={row.best_move_san || "—"} mono highlight />
          <FactRow label="cp_loss" value={row.cp_loss} />
          <FactRow label="Severity" value={row.severity} />
          <FactRow label="Source" value={row.source} mono />
          <FactRow label="Attempts" value={row.attempts ?? 0} />
          <div className="pt-2 border-t" style={{ borderColor: BORDER }}>
            <div className="text-xs text-muted-foreground">Confidence</div>
            <div className="text-lg font-medium" style={{ color: WINE }}>
              {(row.confidence ?? 0).toFixed(3)}
            </div>
            <div className="text-[10px] text-muted-foreground space-y-0.5 mt-1">
              <div>source: {bd.source}</div>
              <div>detector: {bd.detector}</div>
              <div>engine_corroboration: {bd.engine_corroboration}</div>
              <div>cp_loss_certainty: {bd.cp_loss_certainty}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Original */}
      <div className="space-y-1">
        <div className="text-xs text-muted-foreground">Generated commentary</div>
        <div
          className="p-3 rounded text-sm"
          style={{ background: GOLD_BG, color: GOLD_TEXT }}
        >
          {row.text || "—"}
        </div>
      </div>

      {/* Override */}
      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">
          Coach override (replacement text)
        </label>
        <textarea
          value={overrideText}
          onChange={(e) => setOverrideText(e.target.value)}
          rows={3}
          className="w-full p-2 rounded border text-sm"
          style={{ borderColor: BORDER }}
          placeholder="Write the better explanation in plain Indian English..."
        />
        <label className="text-xs text-muted-foreground">
          Coach note (optional — what was wrong / what should the template do)
        </label>
        <textarea
          value={coachNote}
          onChange={(e) => setCoachNote(e.target.value)}
          rows={2}
          className="w-full p-2 rounded border text-sm"
          style={{ borderColor: BORDER }}
          placeholder="e.g. should detect 'protected by counter-attack on h6' — not just 'hanging'"
        />
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={onSave}
            disabled={saving || !overrideText.trim()}
            className="px-3 py-1.5 rounded text-sm font-medium disabled:opacity-50"
            style={{ background: WINE, color: "white" }}
          >
            {saving ? "Saving…" : "Save override"}
          </button>
          {savedFlash && (
            <span className="text-xs text-green-700 flex items-center gap-1">
              <Check className="w-3.5 h-3.5" /> Saved
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function FactRow({ label, value, mono, highlight }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-xs text-muted-foreground w-20 shrink-0">{label}</span>
      <span
        className={mono ? "font-mono text-xs" : "text-sm"}
        style={highlight ? { color: WINE, fontWeight: 500 } : undefined}
      >
        {value === undefined || value === null || value === "" ? "—" : String(value)}
      </span>
    </div>
  );
}
