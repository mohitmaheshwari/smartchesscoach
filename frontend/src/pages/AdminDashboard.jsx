/**
 * AdminDashboard.jsx — Super Admin Dashboard
 *
 * Three tabs: Overview, Users, Feedback Queue
 * Protected by role check (super_admin / admin)
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Loader2,
  Users,
  BarChart3,
  MessageSquareWarning,
  Search,
  UserPlus,
  ShieldCheck,
  Shield,
  User as UserIcon,
  ChevronRight,
  ArrowLeft,
  Flag,
  Check,
  X,
  Clock,
  Eye,
  Gamepad2,
  Brain,
  BookOpen,
} from "lucide-react";

const TAB = { OVERVIEW: "overview", USERS: "users", FEEDBACK: "feedback" };

export default function AdminDashboard({ user }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get("tab") || TAB.OVERVIEW);

  // Check role on mount
  if (user && user.role !== "super_admin" && user.role !== "admin") {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]" data-testid="admin-forbidden">
          <p className="text-red-400 text-sm">Access denied. Admin privileges required.</p>
        </div>
      </Layout>
    );
  }

  const handleTab = (tab) => {
    setActiveTab(tab);
    setSearchParams(tab === TAB.OVERVIEW ? {} : { tab });
  };

  return (
    <Layout user={user}>
      <div className="max-w-6xl mx-auto py-4 px-4 space-y-4" data-testid="admin-dashboard">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Admin Dashboard</h1>
          <div className="flex gap-1 mt-3 bg-zinc-900 rounded-lg p-1 w-fit" data-testid="admin-tabs">
            {[
              { key: TAB.OVERVIEW, label: "Overview", icon: <BarChart3 className="w-3.5 h-3.5" /> },
              { key: TAB.USERS, label: "Users", icon: <Users className="w-3.5 h-3.5" /> },
              { key: TAB.FEEDBACK, label: "Feedback", icon: <MessageSquareWarning className="w-3.5 h-3.5" /> },
            ].map((t) => (
              <button
                key={t.key}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${
                  activeTab === t.key ? "bg-zinc-800 text-white" : "text-zinc-500 hover:text-zinc-300"
                }`}
                onClick={() => handleTab(t.key)}
                data-testid={`admin-tab-${t.key}`}
              >
                {t.icon} {t.label}
              </button>
            ))}
          </div>
        </div>

        {activeTab === TAB.OVERVIEW && <OverviewTab />}
        {activeTab === TAB.USERS && <UsersTab currentUser={user} />}
        {activeTab === TAB.FEEDBACK && <FeedbackTab />}
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

  if (loading) return <LoadingSpinner />;
  if (!data) return <p className="text-red-400 text-sm">Failed to load overview.</p>;

  const stats = [
    { label: "Total Users", value: data.total_users, icon: <Users className="w-4 h-4 text-blue-400" /> },
    { label: "Active (7d)", value: data.active_7d, icon: <UserIcon className="w-4 h-4 text-emerald-400" /> },
    { label: "Active (30d)", value: data.active_30d, icon: <UserIcon className="w-4 h-4 text-teal-400" /> },
    { label: "Total Games", value: data.total_games, icon: <Gamepad2 className="w-4 h-4 text-amber-400" /> },
    { label: "Analyses", value: data.total_analyses, icon: <Brain className="w-4 h-4 text-purple-400" /> },
    { label: "Community Pool", value: data.community_positions, icon: <BookOpen className="w-4 h-4 text-cyan-400" /> },
    { label: "Feedback Pending", value: data.feedback_pending, icon: <Flag className="w-4 h-4 text-red-400" /> },
    { label: "Feedback Total", value: data.feedback_total, icon: <MessageSquareWarning className="w-4 h-4 text-zinc-400" /> },
  ];

  return (
    <div className="space-y-6" data-testid="admin-overview">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {stats.map((s) => (
          <Card key={s.label} className="border-zinc-800 bg-zinc-900/50">
            <CardContent className="p-3">
              <div className="flex items-center gap-2 mb-1">
                {s.icon}
                <span className="text-xs text-muted-foreground">{s.label}</span>
              </div>
              <p className="text-xl font-bold" data-testid={`stat-${s.label.toLowerCase().replace(/[\s()]/g, '-')}`}>
                {s.value}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {data.recent_users?.length > 0 && (
        <div>
          <h3 className="text-sm font-medium mb-2 text-muted-foreground">Recent Signups</h3>
          <div className="space-y-1">
            {data.recent_users.map((u, i) => (
              <div key={i} className="flex items-center justify-between py-1.5 px-3 rounded bg-zinc-900/50 border border-zinc-800/50 text-sm">
                <span>{u.name || u.email || u.user_id}</span>
                <div className="flex items-center gap-2">
                  <RoleBadge role={u.role} />
                  <span className="text-xs text-muted-foreground">{formatDate(u.created_at)}</span>
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

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

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

  // Detail view
  if (selectedUser && detailData) {
    return <UserDetail data={detailData} onBack={() => setSelectedUser(null)} onChangeRole={changeRole} currentUser={currentUser} />;
  }

  return (
    <div className="space-y-4" data-testid="admin-users">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search by name, email..."
            className="pl-9 bg-zinc-900 border-zinc-800"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            data-testid="user-search"
          />
        </div>
        <Select value={roleFilter} onValueChange={setRoleFilter}>
          <SelectTrigger className="w-32 bg-zinc-900 border-zinc-800" data-testid="role-filter">
            <SelectValue placeholder="All roles" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All roles</SelectItem>
            <SelectItem value="user">User</SelectItem>
            <SelectItem value="admin">Admin</SelectItem>
            <SelectItem value="super_admin">Super Admin</SelectItem>
          </SelectContent>
        </Select>
        {currentUser?.role === "super_admin" && (
          <Button size="sm" onClick={() => setShowCreate(true)} data-testid="create-user-btn">
            <UserPlus className="w-4 h-4 mr-1" /> Create
          </Button>
        )}
      </div>

      <p className="text-xs text-muted-foreground">{total} users</p>

      {loading ? (
        <LoadingSpinner />
      ) : (
        <div className="space-y-1">
          {users.map((u) => (
            <div
              key={u.user_id}
              className="flex items-center justify-between py-2 px-3 rounded-lg bg-zinc-900/50 border border-zinc-800/50 cursor-pointer hover:border-primary/30 transition-colors"
              onClick={() => openDetail(u.user_id)}
              data-testid={`user-row-${u.user_id}`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-xs font-bold shrink-0">
                  {(u.name || "?")[0]}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{u.name || u.email}</p>
                  <p className="text-xs text-muted-foreground truncate">{u.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-xs text-muted-foreground">{u.game_count} games</span>
                <RoleBadge role={u.role} />
                <ChevronRight className="w-4 h-4 text-muted-foreground" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create User Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="bg-zinc-900 border-zinc-800" data-testid="create-user-dialog">
          <DialogHeader>
            <DialogTitle>Create New User</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <Input
              placeholder="Name"
              value={createForm.name}
              onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))}
              className="bg-zinc-800 border-zinc-700"
              data-testid="create-name-input"
            />
            <Input
              placeholder="Email"
              type="email"
              value={createForm.email}
              onChange={(e) => setCreateForm((f) => ({ ...f, email: e.target.value }))}
              className="bg-zinc-800 border-zinc-700"
              data-testid="create-email-input"
            />
            <Input
              placeholder="Rating"
              type="number"
              value={createForm.rating}
              onChange={(e) => setCreateForm((f) => ({ ...f, rating: parseInt(e.target.value) || 1200 }))}
              className="bg-zinc-800 border-zinc-700"
              data-testid="create-rating-input"
            />
            <Select value={createForm.role} onValueChange={(v) => setCreateForm((f) => ({ ...f, role: v }))}>
              <SelectTrigger className="bg-zinc-800 border-zinc-700" data-testid="create-role-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="user">User</SelectItem>
                <SelectItem value="admin">Admin</SelectItem>
              </SelectContent>
            </Select>
            <Button className="w-full" onClick={handleCreate} disabled={creating || !createForm.name || !createForm.email} data-testid="create-user-submit">
              {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : "Create User"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
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
    <div className="space-y-4" data-testid="user-detail">
      <button onClick={onBack} className="text-xs text-muted-foreground hover:text-white flex items-center gap-1" data-testid="back-to-users-btn">
        <ArrowLeft className="w-3 h-3" /> Back to users
      </button>

      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-full bg-zinc-800 flex items-center justify-center text-lg font-bold">
          {(u.name || "?")[0]}
        </div>
        <div>
          <h2 className="text-lg font-bold">{u.name}</h2>
          <p className="text-xs text-muted-foreground">{u.email} · {u.user_id}</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <RoleBadge role={u.role} />
          {isSuperAdmin && u.user_id !== currentUser.user_id && (
            <Select value={u.role || "user"} onValueChange={(v) => onChangeRole(u.user_id, v)}>
              <SelectTrigger className="w-28 h-7 text-xs bg-zinc-800 border-zinc-700" data-testid="change-role-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="user">User</SelectItem>
                <SelectItem value="admin">Admin</SelectItem>
                <SelectItem value="super_admin">Super Admin</SelectItem>
              </SelectContent>
            </Select>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Games", value: data.game_count },
          { label: "Analyses", value: data.analysis_count },
          { label: "Rating", value: u.rating || "-" },
          { label: "Joined", value: formatDate(u.created_at) },
        ].map((s) => (
          <Card key={s.label} className="border-zinc-800 bg-zinc-900/50">
            <CardContent className="p-3">
              <p className="text-xs text-muted-foreground">{s.label}</p>
              <p className="text-lg font-bold" data-testid={`detail-${s.label.toLowerCase()}`}>{s.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Habits */}
      {data.habits && (
        <div>
          <h3 className="text-sm font-medium mb-2 text-muted-foreground">Player Habits</h3>
          <Card className="border-zinc-800 bg-zinc-900/50">
            <CardContent className="p-3">
              <div className="grid grid-cols-2 gap-2 text-xs">
                {Object.entries(data.habits)
                  .filter(([k]) => !["user_id", "_id", "updated_at"].includes(k))
                  .slice(0, 8)
                  .map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-muted-foreground">{k.replace(/_/g, " ")}</span>
                      <span className="font-mono">{typeof v === "number" ? v.toFixed?.(2) ?? v : String(v).slice(0, 30)}</span>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Recent Games */}
      {data.recent_games?.length > 0 && (
        <div>
          <h3 className="text-sm font-medium mb-2 text-muted-foreground">Recent Games ({data.game_count} total)</h3>
          <div className="space-y-1">
            {data.recent_games.map((g) => (
              <div key={g.game_id} className="flex items-center justify-between py-1.5 px-3 rounded bg-zinc-900/50 border border-zinc-800/50 text-xs">
                <span>{g.opening || "Unknown"}</span>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-xs">{g.user_color}</Badge>
                  <span className={g.result?.includes("1-0") && g.user_color === "white" || g.result?.includes("0-1") && g.user_color === "black" ? "text-emerald-400" : "text-red-400"}>
                    {g.result}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Opening Progress */}
      {data.opening_progress?.length > 0 && (
        <div>
          <h3 className="text-sm font-medium mb-2 text-muted-foreground">Opening Progress</h3>
          <div className="space-y-1">
            {data.opening_progress.map((op, i) => (
              <div key={i} className="flex items-center justify-between py-1.5 px-3 rounded bg-zinc-900/50 border border-zinc-800/50 text-xs">
                <span>{op.opening_key?.replace(/_/g, " ") || "Unknown"}</span>
                <span className="text-muted-foreground">Mastery: {op.mastery_level || 0}%</span>
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

  useEffect(() => {
    fetchFeedback();
  }, [fetchFeedback]);

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

  const statusColors = {
    pending: "text-amber-400 border-amber-500/30",
    acknowledged: "text-blue-400 border-blue-500/30",
    valid: "text-red-400 border-red-500/30",
    dismissed: "text-zinc-500 border-zinc-700",
  };

  const statusIcons = {
    pending: <Clock className="w-3.5 h-3.5" />,
    acknowledged: <Eye className="w-3.5 h-3.5" />,
    valid: <Flag className="w-3.5 h-3.5" />,
    dismissed: <X className="w-3.5 h-3.5" />,
  };

  return (
    <div className="space-y-4" data-testid="admin-feedback">
      <div className="flex items-center gap-3">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-32 bg-zinc-900 border-zinc-800" data-testid="feedback-status-filter">
            <SelectValue placeholder="All status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All status</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="acknowledged">Acknowledged</SelectItem>
            <SelectItem value="valid">Valid</SelectItem>
            <SelectItem value="dismissed">Dismissed</SelectItem>
          </SelectContent>
        </Select>
        <Select value={sourceFilter} onValueChange={setSourceFilter}>
          <SelectTrigger className="w-28 bg-zinc-900 border-zinc-800" data-testid="feedback-source-filter">
            <SelectValue placeholder="All sources" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All sources</SelectItem>
            <SelectItem value="lab">Lab</SelectItem>
            <SelectItem value="coach">Coach</SelectItem>
          </SelectContent>
        </Select>
        <span className="text-xs text-muted-foreground ml-auto">
          {pending} pending · {total} total
        </span>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : feedback.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground" data-testid="feedback-empty">
          <MessageSquareWarning className="w-8 h-8 mx-auto mb-2 text-zinc-600" />
          <p className="text-sm">No feedback yet.</p>
          <p className="text-xs mt-1">Users can flag moves in Lab and Coach when coaching seems wrong.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {feedback.map((fb) => (
            <Card
              key={fb.feedback_id}
              className={`border-zinc-800 bg-zinc-900/50 cursor-pointer transition-colors ${expandedId === fb.feedback_id ? "border-primary/30" : "hover:border-zinc-700"}`}
              onClick={() => setExpandedId(expandedId === fb.feedback_id ? null : fb.feedback_id)}
              data-testid={`feedback-item-${fb.feedback_id}`}
            >
              <CardContent className="p-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 min-w-0">
                    <Badge variant="outline" className={`text-xs ${statusColors[fb.status]}`}>
                      {statusIcons[fb.status]} <span className="ml-1">{fb.status}</span>
                    </Badge>
                    <Badge variant="outline" className="text-xs">{fb.source}</Badge>
                    <span className="text-sm truncate">{fb.user_name || fb.user_id}</span>
                    {fb.user_rating && <span className="text-xs text-muted-foreground">({fb.user_rating})</span>}
                  </div>
                  <span className="text-xs text-muted-foreground shrink-0">{formatDate(fb.created_at)}</span>
                </div>

                <p className="text-sm mt-2 text-zinc-300 line-clamp-2">{fb.user_note}</p>

                {expandedId === fb.feedback_id && (
                  <div className="mt-3 space-y-2 border-t border-zinc-800 pt-3" onClick={(e) => e.stopPropagation()}>
                    {fb.fen && (
                      <div className="text-xs">
                        <span className="text-muted-foreground">FEN: </span>
                        <code className="bg-zinc-800 px-1 rounded text-xs">{fb.fen}</code>
                      </div>
                    )}
                    {fb.move_san && (
                      <div className="text-xs">
                        <span className="text-muted-foreground">Move: </span>
                        <span className="font-mono">{fb.move_san}</span>
                        {fb.move_number && <span className="text-muted-foreground"> (move {fb.move_number})</span>}
                      </div>
                    )}
                    {fb.coaching_text && (
                      <div className="text-xs bg-zinc-800 p-2 rounded">
                        <span className="text-muted-foreground">Coaching said: </span>
                        <span className="text-zinc-300">{fb.coaching_text}</span>
                      </div>
                    )}
                    {fb.admin_notes && (
                      <div className="text-xs bg-zinc-800 p-2 rounded border border-zinc-700">
                        <span className="text-muted-foreground">Admin notes: </span>
                        <span>{fb.admin_notes}</span>
                      </div>
                    )}

                    <div className="flex items-center gap-2 pt-1">
                      <Input
                        placeholder="Admin notes (optional)..."
                        className="text-xs h-7 bg-zinc-800 border-zinc-700 flex-1"
                        value={adminNotes}
                        onChange={(e) => setAdminNotes(e.target.value)}
                        onClick={(e) => e.stopPropagation()}
                        data-testid="admin-notes-input"
                      />
                      <Button size="sm" variant="outline" className="h-7 text-xs text-blue-400 border-blue-500/30" onClick={() => updateStatus(fb.feedback_id, "acknowledged")} data-testid="btn-acknowledge">
                        <Eye className="w-3 h-3 mr-1" /> Ack
                      </Button>
                      <Button size="sm" variant="outline" className="h-7 text-xs text-red-400 border-red-500/30" onClick={() => updateStatus(fb.feedback_id, "valid")} data-testid="btn-valid">
                        <Flag className="w-3 h-3 mr-1" /> Valid
                      </Button>
                      <Button size="sm" variant="outline" className="h-7 text-xs text-zinc-400 border-zinc-700" onClick={() => updateStatus(fb.feedback_id, "dismissed")} data-testid="btn-dismiss">
                        <X className="w-3 h-3 mr-1" /> Dismiss
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

/* ============================================================
 * SHARED COMPONENTS
 * ============================================================ */
const RoleBadge = ({ role }) => {
  const config = {
    super_admin: { icon: <ShieldCheck className="w-3 h-3" />, color: "text-amber-400 border-amber-500/30", label: "Super Admin" },
    admin: { icon: <Shield className="w-3 h-3" />, color: "text-blue-400 border-blue-500/30", label: "Admin" },
    user: { icon: <UserIcon className="w-3 h-3" />, color: "text-zinc-400 border-zinc-700", label: "User" },
  };
  const c = config[role] || config.user;
  return (
    <Badge variant="outline" className={`text-xs ${c.color} flex items-center gap-1`}>
      {c.icon} {c.label}
    </Badge>
  );
};

const LoadingSpinner = () => (
  <div className="flex items-center justify-center py-12">
    <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
  </div>
);

const formatDate = (dateStr) => {
  if (!dateStr) return "-";
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "-";
  }
};
