/**
 * OpeningsOverview.jsx - Admin View for All Openings
 * 
 * Displays all openings from the library with their data
 * to verify admin content is pulling correctly.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  BookOpen,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Search,
  Settings,
  ExternalLink,
  Target,
  Swords,
  Shield,
  Loader2
} from "lucide-react";

const OpeningsOverview = ({ user }) => {
  const navigate = useNavigate();
  const [openings, setOpenings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [expandedOpening, setExpandedOpening] = useState(null);
  const [openingDetails, setOpeningDetails] = useState({});
  const [loadingDetails, setLoadingDetails] = useState({});

  useEffect(() => {
    fetchOpenings();
  }, []);

  const fetchOpenings = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API}/admin/openings`);
      const data = await response.json();
      setOpenings(data.openings || []);
    } catch (err) {
      setError("Failed to fetch openings");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchOpeningDetails = async (openingKey) => {
    if (openingDetails[openingKey]) {
      return; // Already fetched
    }

    setLoadingDetails(prev => ({ ...prev, [openingKey]: true }));
    try {
      const response = await fetch(`${API}/openings/${openingKey}`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("token")}`
        }
      });
      const data = await response.json();
      setOpeningDetails(prev => ({ ...prev, [openingKey]: data.opening }));
    } catch (err) {
      console.error(`Failed to fetch details for ${openingKey}:`, err);
    } finally {
      setLoadingDetails(prev => ({ ...prev, [openingKey]: false }));
    }
  };

  const toggleExpand = async (openingKey) => {
    if (expandedOpening === openingKey) {
      setExpandedOpening(null);
    } else {
      setExpandedOpening(openingKey);
      await fetchOpeningDetails(openingKey);
    }
  };

  const filteredOpenings = openings.filter(o =>
    o.opening_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    o.opening_key?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getSourceBadgeColor = (source) => {
    switch (source) {
      case "library": return "bg-blue-500/20 text-blue-400 border-blue-500/30";
      case "mastery": return "bg-purple-500/20 text-purple-400 border-purple-500/30";
      case "plans": return "bg-green-500/20 text-green-400 border-green-500/30";
      default: return "bg-zinc-500/20 text-zinc-400 border-zinc-500/30";
    }
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-6xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <BookOpen className="w-6 h-6 text-amber-500" />
              Opening Library Overview
            </h1>
            <p className="text-zinc-400 mt-1">
              {openings.length} openings loaded • Verify admin content
            </p>
          </div>
          <Button
            onClick={() => navigate("/admin/openings")}
            variant="outline"
            className="border-zinc-700 hover:bg-zinc-800"
          >
            <Settings className="w-4 h-4 mr-2" />
            Admin Editor
          </Button>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <Input
            placeholder="Search openings..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10 bg-zinc-900 border-zinc-700"
          />
        </div>

        {/* Error */}
        {error && (
          <Card className="bg-red-900/20 border-red-500/30">
            <CardContent className="p-4 text-red-400">
              {error}
            </CardContent>
          </Card>
        )}

        {/* Openings List */}
        <div className="space-y-3">
          {filteredOpenings.map((opening) => {
            const isExpanded = expandedOpening === opening.opening_key;
            const details = openingDetails[opening.opening_key];
            const isLoadingDetails = loadingDetails[opening.opening_key];

            return (
              <Card
                key={opening.opening_key}
                className="bg-zinc-900/50 border-zinc-800 hover:border-zinc-700 transition-colors"
              >
                <CardHeader
                  className="cursor-pointer"
                  onClick={() => toggleExpand(opening.opening_key)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
                        <BookOpen className="w-5 h-5 text-amber-500" />
                      </div>
                      <div>
                        <CardTitle className="text-lg text-white">
                          {opening.opening_name}
                        </CardTitle>
                        <p className="text-sm text-zinc-500 font-mono">
                          {opening.opening_key}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      {/* Sources */}
                      <div className="flex gap-1">
                        {opening.sources?.map(source => (
                          <Badge
                            key={source}
                            variant="outline"
                            className={`text-xs ${getSourceBadgeColor(source)}`}
                          >
                            {source}
                          </Badge>
                        ))}
                      </div>

                      {/* Admin Override Indicator */}
                      {opening.updated_at ? (
                        <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                          <CheckCircle className="w-3 h-3 mr-1" />
                          Admin Override
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-zinc-500 border-zinc-700">
                          Static Only
                        </Badge>
                      )}

                      {isExpanded ? (
                        <ChevronUp className="w-5 h-5 text-zinc-500" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-zinc-500" />
                      )}
                    </div>
                  </div>
                </CardHeader>

                {/* Expanded Details */}
                {isExpanded && (
                  <CardContent className="border-t border-zinc-800 pt-4">
                    {isLoadingDetails ? (
                      <div className="flex items-center justify-center py-8">
                        <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
                      </div>
                    ) : details ? (
                      <div className="space-y-4">
                        {/* Quick Stats */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                          <StatCard
                            label="Key Ideas"
                            value={details.key_ideas?.length || 0}
                            icon={Target}
                            color="amber"
                            hasData={details.key_ideas?.length > 0}
                          />
                          <StatCard
                            label="Traps"
                            value={details.traps?.length || 0}
                            icon={Swords}
                            color="red"
                            hasData={details.traps?.length > 0}
                          />
                          <StatCard
                            label="Main Line Moves"
                            value={details.main_line?.length || 0}
                            icon={BookOpen}
                            color="blue"
                            hasData={details.main_line?.length > 0}
                          />
                          <StatCard
                            label="What If"
                            value={details.what_if?.length || 0}
                            icon={Shield}
                            color="purple"
                            hasData={details.what_if?.length > 0}
                          />
                        </div>

                        {/* Description */}
                        {details.description && (
                          <div className="bg-zinc-800/50 rounded-lg p-3">
                            <p className="text-sm text-zinc-400 font-medium mb-1">Description</p>
                            <p className="text-white">{details.description}</p>
                          </div>
                        )}

                        {/* Key Ideas */}
                        {details.key_ideas?.length > 0 && (
                          <div className="bg-zinc-800/50 rounded-lg p-3">
                            <p className="text-sm text-zinc-400 font-medium mb-2">Key Ideas</p>
                            <ul className="space-y-1">
                              {details.key_ideas.map((idea, i) => (
                                <li key={i} className="flex items-start gap-2 text-white">
                                  <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                                  <span>{idea}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Main Line Preview */}
                        {details.main_line?.length > 0 && (
                          <div className="bg-zinc-800/50 rounded-lg p-3">
                            <p className="text-sm text-zinc-400 font-medium mb-2">Main Line</p>
                            <div className="flex flex-wrap gap-2">
                              {details.main_line.slice(0, 10).map((step, i) => (
                                <div
                                  key={i}
                                  className="bg-zinc-700/50 rounded px-2 py-1"
                                  title={step.explanation}
                                >
                                  <span className="text-zinc-500 text-sm mr-1">
                                    {Math.floor(i / 2) + 1}{i % 2 === 0 ? "." : "..."}
                                  </span>
                                  <span className="text-white font-mono">{step.move}</span>
                                </div>
                              ))}
                              {details.main_line.length > 10 && (
                                <span className="text-zinc-500 text-sm self-center">
                                  +{details.main_line.length - 10} more
                                </span>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Traps */}
                        {details.traps?.length > 0 && (
                          <div className="bg-zinc-800/50 rounded-lg p-3">
                            <p className="text-sm text-zinc-400 font-medium mb-2">Traps</p>
                            <div className="space-y-2">
                              {details.traps.map((trap, i) => (
                                <div key={i} className="flex items-center gap-2 text-white">
                                  <Swords className="w-4 h-4 text-red-500 flex-shrink-0" />
                                  <span className="font-medium">{trap.name}</span>
                                  {trap.difficulty && (
                                    <Badge variant="outline" className="text-xs">
                                      {trap.difficulty}
                                    </Badge>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Common Mistakes */}
                        {details.common_mistakes?.length > 0 && (
                          <div className="bg-zinc-800/50 rounded-lg p-3">
                            <p className="text-sm text-zinc-400 font-medium mb-2">Common Mistakes</p>
                            <ul className="space-y-1">
                              {details.common_mistakes.map((mistake, i) => (
                                <li key={i} className="flex items-start gap-2 text-white">
                                  <XCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
                                  <span>{typeof mistake === 'string' ? mistake : mistake.mistake}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Data Completeness Warning */}
                        {(!details.key_ideas?.length || !details.main_line?.length) && (
                          <div className="flex items-center gap-2 text-amber-400 bg-amber-500/10 rounded-lg p-3">
                            <AlertTriangle className="w-4 h-4" />
                            <span className="text-sm">
                              Missing data: 
                              {!details.key_ideas?.length && " Key Ideas"}
                              {!details.main_line?.length && " Main Line"}
                              {!details.traps?.length && " Traps"}
                            </span>
                          </div>
                        )}

                        {/* Actions */}
                        <div className="flex gap-2 pt-2">
                          <Button
                            size="sm"
                            onClick={() => navigate(`/openings/${opening.opening_key}`)}
                            className="bg-amber-600 hover:bg-amber-700"
                          >
                            <ExternalLink className="w-4 h-4 mr-1" />
                            View Lesson Page
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => navigate("/admin/openings")}
                            className="border-zinc-700 hover:bg-zinc-800"
                          >
                            <Settings className="w-4 h-4 mr-1" />
                            Edit in Admin
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <p className="text-zinc-500 text-center py-4">
                        Failed to load details
                      </p>
                    )}
                  </CardContent>
                )}
              </Card>
            );
          })}
        </div>

        {/* Empty State */}
        {filteredOpenings.length === 0 && !loading && (
          <Card className="bg-zinc-900/50 border-zinc-800">
            <CardContent className="p-8 text-center">
              <BookOpen className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-400">
                {searchTerm
                  ? "No openings match your search"
                  : "No openings found in library"}
              </p>
            </CardContent>
          </Card>
        )}

        {/* Summary Stats */}
        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardContent className="p-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-zinc-400">
                Total: {openings.length} openings
              </span>
              <span className="text-zinc-400">
                With Admin Override: {openings.filter(o => o.updated_at).length}
              </span>
              <span className="text-zinc-400">
                Static Only: {openings.filter(o => !o.updated_at).length}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

// Stat Card Component
const StatCard = ({ label, value, icon: Icon, color, hasData }) => {
  const colorClasses = {
    amber: "text-amber-500 bg-amber-500/10",
    red: "text-red-500 bg-red-500/10",
    blue: "text-blue-500 bg-blue-500/10",
    purple: "text-purple-500 bg-purple-500/10",
    green: "text-green-500 bg-green-500/10"
  };

  return (
    <div className={`rounded-lg p-3 ${hasData ? colorClasses[color].split(" ")[1] : "bg-zinc-800/50"}`}>
      <div className="flex items-center gap-2">
        <Icon className={`w-4 h-4 ${hasData ? colorClasses[color].split(" ")[0] : "text-zinc-600"}`} />
        <span className={`text-xl font-bold ${hasData ? "text-white" : "text-zinc-600"}`}>
          {value}
        </span>
      </div>
      <p className="text-xs text-zinc-500 mt-1">{label}</p>
    </div>
  );
};

export default OpeningsOverview;
