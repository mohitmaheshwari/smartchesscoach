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
  ArrowLeft, Flag, X, Clock, Eye, Gamepad2, Brain, BookOpen, Download,
} from "lucide-react";

const WINE = "#722F37";
const GOLD_TEXT = "#8B6F1F";
const GOLD_BG = "rgba(203,161,53,0.1)";
const BORDER = "hsl(35 10% 87%)";

export default function AdminDashboard({ user }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get("tab") || "overview");

  if (user && user.role !== "super_admin" && user.role !== "admin") {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]" data-testid="admin-forbidden">
          <p className="text-sm" style={{ color: WINE }}>Access denied. Admin privileges required.</p>
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
  ];

  return (
    <Layout user={user}>
      <div className="max-w-4xl mx-auto py-6 px-4 space-y-6" data-testid="admin-dashboard">
        {/* Header */}
        <div>
          <h1 className="text-2xl text-foreground tracking-tight" style={{ fontFamily: "'Playfair Display', serif" }}>
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
              <p className="text-xl text-foreground font-light" style={{ fontFamily: "'Playfair Display', serif" }} data-testid={`stat-${s.label.toLowerCase().replace(/[\s()]/g, '-')}`}>
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
            <h3 className="text-lg text-foreground" style={{ fontFamily: "'Playfair Display', serif" }}>Create New User</h3>
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
 * USER DETAIL VIEW
 * ============================================================ */
const UserDetail = ({ data, onBack, onChangeRole, currentUser }) => {
  const u = data.user;
  const isSuperAdmin = currentUser?.role === "super_admin";

  return (
    <div className="space-y-5" data-testid="user-detail">
      <button onClick={onBack} className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors" data-testid="back-to-users-btn">
        <ArrowLeft className="w-3 h-3" /> Back to users
      </button>

      {/* User Header */}
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-full flex items-center justify-center text-lg text-white font-light" style={{ background: WINE }}>
          {(u.name || "?")[0]}
        </div>
        <div className="flex-1">
          <h2 className="text-lg text-foreground" style={{ fontFamily: "'Playfair Display', serif" }}>{u.name}</h2>
          <p className="text-[10px] text-muted-foreground font-mono">{u.email} · {u.user_id}</p>
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

      {/* Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Games", value: data.game_count },
          { label: "Analyses", value: data.analysis_count },
          { label: "Rating", value: u.rating || "—" },
          { label: "Joined", value: formatDate(u.created_at) },
        ].map((s) => (
          <Card key={s.label}>
            <div className="p-3">
              <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider">{s.label}</p>
              <p className="text-lg text-foreground font-light" style={{ fontFamily: "'Playfair Display', serif" }} data-testid={`detail-${s.label.toLowerCase()}`}>{s.value}</p>
            </div>
          </Card>
        ))}
      </div>

      {/* Habits */}
      {data.habits && (
        <div>
          <SectionLabel>Player Habits</SectionLabel>
          <Card>
            <div className="p-3">
              <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
                {Object.entries(data.habits)
                  .filter(([k]) => !["user_id", "_id", "updated_at"].includes(k))
                  .slice(0, 8)
                  .map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-muted-foreground font-light">{k.replace(/_/g, " ")}</span>
                      <span className="font-mono text-foreground">{typeof v === "number" ? v.toFixed?.(2) ?? v : String(v).slice(0, 30)}</span>
                    </div>
                  ))}
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Recent Games */}
      {data.recent_games?.length > 0 && (
        <div>
          <SectionLabel>Recent Games ({data.game_count} total)</SectionLabel>
          <div className="space-y-1">
            {data.recent_games.map((g) => {
              const won = (g.result?.includes("1-0") && g.user_color === "white") || (g.result?.includes("0-1") && g.user_color === "black");
              return (
                <div key={g.game_id} className="flex items-center justify-between py-2 px-3 rounded-sm bg-white border text-xs" style={{ borderColor: BORDER }}>
                  <span className="text-foreground font-light">{g.opening || "Unknown"}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[9px] px-1.5 py-0.5 rounded-sm border font-mono" style={{ borderColor: BORDER }}>{g.user_color}</span>
                    <span className="font-mono" style={{ color: won ? "#16a34a" : WINE }}>{g.result}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Opening Progress */}
      {data.opening_progress?.length > 0 && (
        <div>
          <SectionLabel>Opening Progress</SectionLabel>
          <div className="space-y-1">
            {data.opening_progress.map((op, i) => (
              <div key={i} className="flex items-center justify-between py-2 px-3 rounded-sm bg-white border text-xs" style={{ borderColor: BORDER }}>
                <span className="text-foreground font-light">{op.opening_key?.replace(/_/g, " ") || "Unknown"}</span>
                <span className="text-muted-foreground font-mono">Mastery: {op.mastery_level || 0}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
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
  const [exporting, setExporting] = useState(false);

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

  const handleExport = async () => {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter && statusFilter !== "all") params.set("status", statusFilter);
      if (sourceFilter && sourceFilter !== "all") params.set("source", sourceFilter);
      const res = await fetch(`${API}/admin/feedback/export?${params}`, { credentials: "include" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(`Export failed: ${err.detail || res.statusText}`);
        return;
      }
      const data = await res.json();
      const jsonStr = JSON.stringify(data, null, 2);
      const blob = new Blob([jsonStr], { type: "application/json" });
      const filename = `feedback-export-${new Date().toISOString().slice(0, 10)}.json`;

      // Try native download
      if (window.navigator?.msSaveOrOpenBlob) {
        window.navigator.msSaveOrOpenBlob(blob, filename);
      } else {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.style.display = "none";
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        // Delay cleanup for Safari
        setTimeout(() => {
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        }, 200);
      }
    } catch (e) {
      alert(`Export error: ${e.message}`);
    } finally {
      setExporting(false);
    }
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
          disabled={exporting || total === 0}
          data-testid="export-feedback-btn"
        >
          {exporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
          Export JSON
        </button>
      </div>

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
