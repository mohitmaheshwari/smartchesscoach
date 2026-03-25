/**
 * OpeningsOverview.jsx - Opening Theory Tree Browser
 * 
 * Displays all openings from the JSON theory tree with their
 * variations, move depths, plans, and critical positions.
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
  ChevronDown,
  ChevronUp,
  Search,
  Loader2,
  GitBranch,
  Layers,
  Swords,
  Crown,
  Shield,
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
      const token = localStorage.getItem("token");
      const response = await fetch(`${API}/admin/openings`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
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
    if (openingDetails[openingKey]) return;
    setLoadingDetails((prev) => ({ ...prev, [openingKey]: true }));
    try {
      const token = localStorage.getItem("token");
      const response = await fetch(`${API}/admin/openings/${openingKey}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await response.json();
      setOpeningDetails((prev) => ({ ...prev, [openingKey]: data.feedback }));
    } catch (err) {
      console.error(`Failed to fetch details for ${openingKey}:`, err);
    } finally {
      setLoadingDetails((prev) => ({ ...prev, [openingKey]: false }));
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

  const filteredOpenings = openings.filter(
    (o) =>
      o.opening_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      o.opening_key?.toLowerCase().includes(searchTerm.toLowerCase())
  );

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
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2" data-testid="openings-overview-title">
            <BookOpen className="w-6 h-6 text-amber-500" />
            Opening Theory Tree
          </h1>
          <p className="text-zinc-400 mt-1">
            {openings.length} openings with deep theory
          </p>
        </div>

        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <Input
            placeholder="Search openings..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10 bg-zinc-900 border-zinc-700"
            data-testid="openings-search"
          />
        </div>

        {error && (
          <Card className="bg-red-900/20 border-red-500/30">
            <CardContent className="p-4 text-red-400">{error}</CardContent>
          </Card>
        )}

        <div className="space-y-3" data-testid="openings-list">
          {filteredOpenings.map((opening) => {
            const isExpanded = expandedOpening === opening.opening_key;
            const details = openingDetails[opening.opening_key];
            const isLoadingDetail = loadingDetails[opening.opening_key];

            return (
              <Card
                key={opening.opening_key}
                className="bg-zinc-900/50 border-zinc-800 hover:border-zinc-700 transition-colors"
                data-testid={`opening-card-${opening.opening_key}`}
              >
                <CardHeader
                  className="cursor-pointer py-4"
                  onClick={() => toggleExpand(opening.opening_key)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
                        <BookOpen className="w-5 h-5 text-amber-500" />
                      </div>
                      <div>
                        <CardTitle className="text-base text-white">
                          {opening.opening_name}
                        </CardTitle>
                        <p className="text-xs text-zinc-500 font-mono mt-0.5">
                          {opening.eco_prefix?.join(", ")}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className="text-xs bg-blue-500/10 text-blue-400 border-blue-500/30"
                      >
                        <GitBranch className="w-3 h-3 mr-1" />
                        {opening.variations_count} var
                      </Badge>
                      <Badge
                        variant="outline"
                        className="text-xs bg-amber-500/10 text-amber-400 border-amber-500/30"
                      >
                        <Layers className="w-3 h-3 mr-1" />
                        {opening.max_depth} moves
                      </Badge>
                      {isExpanded ? (
                        <ChevronUp className="w-5 h-5 text-zinc-500" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-zinc-500" />
                      )}
                    </div>
                  </div>
                </CardHeader>

                {isExpanded && (
                  <CardContent className="border-t border-zinc-800 pt-4">
                    {isLoadingDetail ? (
                      <div className="flex items-center justify-center py-8">
                        <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
                      </div>
                    ) : details ? (
                      <div className="space-y-4">
                        {/* Plans */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {details.white_plan && (
                            <div className="bg-zinc-800/50 rounded-lg p-3">
                              <p className="text-xs text-zinc-500 font-medium mb-1 flex items-center gap-1">
                                <Crown className="w-3 h-3" /> White's Plan
                              </p>
                              <p className="text-sm text-white">{details.white_plan}</p>
                            </div>
                          )}
                          {details.black_plan && (
                            <div className="bg-zinc-800/50 rounded-lg p-3">
                              <p className="text-xs text-zinc-500 font-medium mb-1 flex items-center gap-1">
                                <Shield className="w-3 h-3" /> Black's Plan
                              </p>
                              <p className="text-sm text-white">{details.black_plan}</p>
                            </div>
                          )}
                        </div>

                        {/* Main Line */}
                        {details.main_line?.length > 0 && (
                          <div className="bg-zinc-800/50 rounded-lg p-3">
                            <p className="text-xs text-zinc-500 font-medium mb-2">
                              Defining Moves
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                              {details.main_line.map((move, i) => (
                                <span
                                  key={i}
                                  className="bg-zinc-700/60 rounded px-2 py-0.5 text-sm"
                                >
                                  <span className="text-zinc-500 mr-1">
                                    {Math.floor(i / 2) + 1}
                                    {i % 2 === 0 ? "." : "..."}
                                  </span>
                                  <span className="text-white font-mono">{move}</span>
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Variations */}
                        {details.variations?.length > 0 && (
                          <div className="bg-zinc-800/50 rounded-lg p-3">
                            <p className="text-xs text-zinc-500 font-medium mb-2">
                              Variations ({details.variations.length})
                            </p>
                            <div className="space-y-2">
                              {details.variations.map((v, i) => (
                                <VariationRow key={v.key || i} variation={v} />
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Common Learnings */}
                        {details.common_learnings?.length > 0 && (
                          <div className="bg-zinc-800/50 rounded-lg p-3">
                            <p className="text-xs text-zinc-500 font-medium mb-2">
                              Key Takeaways
                            </p>
                            <ul className="space-y-1">
                              {details.common_learnings.map((idea, i) => (
                                <li
                                  key={i}
                                  className="text-sm text-zinc-300 flex items-start gap-2"
                                >
                                  <span className="text-amber-500 mt-0.5">*</span>
                                  {idea}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Traps */}
                        {details.traps?.length > 0 && (
                          <div className="bg-zinc-800/50 rounded-lg p-3">
                            <p className="text-xs text-zinc-500 font-medium mb-2">
                              Traps
                            </p>
                            <div className="space-y-1">
                              {details.traps.map((trap, i) => (
                                <div
                                  key={i}
                                  className="flex items-center gap-2 text-sm text-white"
                                >
                                  <Swords className="w-3 h-3 text-red-500 flex-shrink-0" />
                                  <span>{trap.name}</span>
                                  {trap.difficulty && (
                                    <Badge
                                      variant="outline"
                                      className="text-[10px] px-1.5 py-0"
                                    >
                                      {trap.difficulty}
                                    </Badge>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Action */}
                        <div className="pt-1">
                          <Button
                            size="sm"
                            onClick={() => navigate(`/openings/${opening.opening_key}`)}
                            className="bg-amber-600 hover:bg-amber-700"
                            data-testid={`view-lesson-${opening.opening_key}`}
                          >
                            Open Lesson
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

        {filteredOpenings.length === 0 && !loading && (
          <Card className="bg-zinc-900/50 border-zinc-800">
            <CardContent className="p-8 text-center">
              <BookOpen className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-400">
                {searchTerm
                  ? "No openings match your search"
                  : "No openings found"}
              </p>
            </CardContent>
          </Card>
        )}

        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardContent className="p-4">
            <div className="flex items-center justify-between text-sm text-zinc-400">
              <span>Total: {openings.length} openings</span>
              <span>
                {openings.reduce((a, o) => a + (o.variations_count || 0), 0)}{" "}
                variations
              </span>
              <span>
                Deepest: {Math.max(...openings.map((o) => o.max_depth || 0))} moves
              </span>
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

const VariationRow = ({ variation }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-zinc-900/50 rounded-lg overflow-hidden">
      <div
        className="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-zinc-800/50"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <GitBranch className="w-3.5 h-3.5 text-blue-400" />
          <span className="text-sm text-white">{variation.name}</span>
        </div>
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className="text-[10px] px-1.5 py-0 bg-zinc-800 border-zinc-700"
          >
            {variation.total_moves} moves
          </Badge>
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-zinc-500" />
          ) : (
            <ChevronDown className="w-4 h-4 text-zinc-500" />
          )}
        </div>
      </div>
      {expanded && (
        <div className="px-3 pb-3 space-y-2">
          {variation.white_plan && (
            <p className="text-xs text-zinc-400">
              <span className="text-zinc-500">White:</span> {variation.white_plan}
            </p>
          )}
          {variation.black_plan && (
            <p className="text-xs text-zinc-400">
              <span className="text-zinc-500">Black:</span> {variation.black_plan}
            </p>
          )}
          <div className="flex flex-wrap gap-1">
            {variation.moves?.map((move, i) => (
              <span
                key={i}
                className="bg-zinc-800 rounded px-1.5 py-0.5 text-xs font-mono text-zinc-300"
              >
                {i % 2 === 0 && (
                  <span className="text-zinc-600 mr-0.5">
                    {Math.floor(i / 2) + 1}.
                  </span>
                )}
                {move}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default OpeningsOverview;
