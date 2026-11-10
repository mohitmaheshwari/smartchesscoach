// Built by coach_plan_service.build_moment on a real production position
// (2026-11-10) with a fake engine that prefers Nc3. Regenerate, don't hand-edit.
const developmentMoment = {
 "key": "g1:13:e3g3",
 "quality_id": "knowledge:development",
 "kind": "development",
 "pattern": null,
 "game_id": "g1",
 "date": "2026-11-01",
 "color": "white",
 "san": "Qg3",
 "uci": "e3g3",
 "from": "e3",
 "to": "g3",
 "moved": "queen",
 "fen_before": "rnb1kb1r/ppp2ppp/8/3qp3/8/4Q3/PP1P1PPP/RNB1KBNR w KQkq - 0 7",
 "fen_after": "rnb1kb1r/ppp2ppp/8/3qp3/8/6Q1/PP1P1PPP/RNB1KBNR b KQkq - 1 7",
 "fen_reply": null,
 "reply_san": null,
 "reply_from": null,
 "think_s": null,
 "costs_result": false,
 "intents": [
  {
   "kind": "defend",
   "sq": "g2",
   "piece": "pawn",
   "verdict": "already_guarded",
   "attackers": [
    {
     "sq": "d5",
     "piece": "queen"
    }
   ],
   "guards": [
    {
     "sq": "f1",
     "piece": "bishop",
     "pinned": false,
     "pinned_by": null
    }
   ]
  },
  {
   "kind": "attack",
   "sq": "e5",
   "piece": "pawn",
   "already_attacked": true,
   "guarded_by_them": true
  },
  {
   "kind": "attack",
   "sq": "g7",
   "piece": "pawn",
   "already_attacked": false,
   "guarded_by_them": true
  }
 ],
 "escape": false,
 "develops": false,
 "best": {
  "uci": "b1c3",
  "san": "Nc3",
  "frees": [],
  "attacks": [
   "d5"
  ],
  "safe": true
 },
 "test": {
  "kind": "find_move",
  "accept": [
   "b1c3"
  ],
  "best": {
   "uci": "b1c3",
   "san": "Nc3"
  },
  "explain": {
   "targets": [],
   "mate": false,
   "home": [
    {
     "sq": "b1",
     "piece": "knight"
    },
    {
     "sq": "c1",
     "piece": "bishop"
    },
    {
     "sq": "f1",
     "piece": "bishop"
    },
    {
     "sq": "g1",
     "piece": "knight"
    }
   ]
  }
 },
 "practice": {
  "from": null,
  "moves": {
   "e3g3": {
    "san": "Qg3",
    "loss": 300,
    "safe": true,
    "takers": [],
    "guards": [
     "f2",
     "g2",
     "h2"
    ],
    "attacks": [
     "e5",
     "g7"
    ],
    "frees": []
   },
   "g1f3": {
    "san": "Nf3",
    "loss": 300,
    "safe": false,
    "takers": [
     {
      "sq": "d5",
      "piece": "queen",
      "kind": "far_diagonal"
     }
    ],
    "guards": [
     "e1",
     "d2",
     "h2"
    ],
    "attacks": [
     "e5"
    ],
    "frees": []
   },
   "b1c3": {
    "san": "Nc3",
    "loss": 0,
    "safe": true,
    "takers": [],
    "guards": [
     "a2"
    ],
    "attacks": [
     "d5"
    ],
    "frees": []
   }
  }
 }
};
export default developmentMoment;
