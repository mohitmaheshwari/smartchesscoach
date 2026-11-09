// Real facts for Qf3 (test child, 2026-11-05), from python-chess + depth-16 Stockfish on prod.
const qf3Moment = {
 "key": "g86164614:15",
 "quality_id": "gap:piece_safety:destination_safety_exact",
 "kind": "landing",
 "pattern": null,
 "date": "2026-11-05",
 "color": "white",
 "san": "Qf3",
 "uci": "d1f3",
 "from": "d1",
 "to": "f3",
 "moved": "queen",
 "fen_before": "r1bqk2r/pp1p1ppp/4pn2/4n3/1b2P3/1BN5/PPP2PPP/R1BQK1NR w KQkq - 7 8",
 "fen_after": "r1bqk2r/pp1p1ppp/4pn2/4n3/1b2P3/1BN2Q2/PPP2PPP/R1B1K1NR b KQkq - 8 8",
 "fen_reply": "r1bqk2r/pp1p1ppp/4pn2/8/1b2P3/1BN2n2/PPP2PPP/R1B1K1NR w KQkq - 0 9",
 "reply_san": "Nxf3+",
 "reply_from": "e5",
 "think_s": 24.0,
 "intents": [
  {
   "kind": "defend",
   "sq": "c3",
   "piece": "knight",
   "verdict": "already_guarded",
   "attackers": [
    {
     "sq": "b4",
     "piece": "bishop"
    }
   ],
   "guards": [
    {
     "sq": "b2",
     "piece": "pawn",
     "pinned": false,
     "pinned_by": null
    }
   ]
  },
  {
   "kind": "defend",
   "sq": "e4",
   "piece": "pawn",
   "verdict": "needed",
   "attackers": [
    {
     "sq": "f6",
     "piece": "knight"
    }
   ],
   "guards": [
    {
     "sq": "c3",
     "piece": "knight",
     "pinned": true,
     "pinned_by": {
      "sq": "b4",
      "piece": "bishop"
     }
    }
   ]
  },
  {
   "kind": "attack",
   "sq": "f6",
   "piece": "knight",
   "already_attacked": false,
   "guarded_by_them": true
  }
 ],
 "escape": false,
 "develops": true,
 "test": {
  "kind": "tap_pieces",
  "answer": [
   {
    "sq": "e5",
    "piece": "knight",
    "kind": "knight",
    "path": []
   }
  ]
 },
 "cost": {
  "can_recapture": true,
  "lost": "queen",
  "won": "knight"
 },
 "practice": {
  "from": "d1",
  "moves": {
   "d1e2": {
    "san": "Qe2",
    "loss": 95,
    "safe": true,
    "takers": [],
    "guards": [
     "e1",
     "c2",
     "f2",
     "e4"
    ],
    "attacks": []
   },
   "d1d4": {
    "san": "Qd4",
    "loss": 104,
    "safe": true,
    "takers": [],
    "guards": [
     "f2",
     "c3",
     "e4"
    ],
    "attacks": [
     "b4",
     "e5",
     "a7",
     "d7"
    ]
   },
   "d1d2": {
    "san": "Qd2",
    "loss": 155,
    "safe": true,
    "takers": [],
    "guards": [
     "c1",
     "e1",
     "c2",
     "f2",
     "c3"
    ],
    "attacks": [
     "d7"
    ]
   },
   "d1f3": {
    "san": "Qf3",
    "loss": 583,
    "safe": false,
    "takers": [
     {
      "sq": "e5",
      "piece": "knight",
      "kind": "knight"
     }
    ],
    "guards": [
     "f2",
     "g2",
     "c3",
     "e4"
    ],
    "attacks": [
     "f6"
    ]
   },
   "d1d3": {
    "san": "Qd3",
    "loss": 594,
    "safe": false,
    "takers": [
     {
      "sq": "e5",
      "piece": "knight",
      "kind": "knight"
     }
    ],
    "guards": [
     "c2",
     "c3",
     "e4"
    ],
    "attacks": [
     "d7"
    ]
   },
   "d1d5": {
    "san": "Qd5",
    "loss": 682,
    "safe": false,
    "takers": [
     {
      "sq": "e6",
      "piece": "pawn",
      "kind": "near"
     },
     {
      "sq": "f6",
      "piece": "knight",
      "kind": "knight"
     }
    ],
    "guards": [
     "b3",
     "e4"
    ],
    "attacks": [
     "e5",
     "e6",
     "b7",
     "d7"
    ]
   },
   "d1d6": {
    "san": "Qd6",
    "loss": 692,
    "safe": false,
    "takers": [
     {
      "sq": "b4",
      "piece": "bishop",
      "kind": "far_diagonal"
     }
    ],
    "guards": [],
    "attacks": [
     "b4",
     "e5",
     "e6",
     "d7"
    ]
   },
   "d1h5": {
    "san": "Qh5",
    "loss": 717,
    "safe": false,
    "takers": [
     {
      "sq": "f6",
      "piece": "knight",
      "kind": "knight"
     }
    ],
    "guards": [
     "h2"
    ],
    "attacks": [
     "e5",
     "f7",
     "h7"
    ]
   },
   "d1d7": {
    "san": "Qxd7+",
    "loss": 737,
    "safe": false,
    "takers": [
     {
      "sq": "e5",
      "piece": "knight",
      "kind": "knight"
     },
     {
      "sq": "f6",
      "piece": "knight",
      "kind": "knight"
     },
     {
      "sq": "c8",
      "piece": "bishop",
      "kind": "near"
     },
     {
      "sq": "d8",
      "piece": "queen",
      "kind": "near"
     },
     {
      "sq": "e8",
      "piece": "king",
      "kind": "near"
     }
    ],
    "guards": [],
    "attacks": [
     "e6",
     "b7",
     "f7",
     "c8",
     "d8",
     "e8"
    ]
   },
   "d1g4": {
    "san": "Qg4",
    "loss": 749,
    "safe": false,
    "takers": [
     {
      "sq": "e5",
      "piece": "knight",
      "kind": "knight"
     },
     {
      "sq": "f6",
      "piece": "knight",
      "kind": "knight"
     }
    ],
    "guards": [
     "g2",
     "e4"
    ],
    "attacks": [
     "e6",
     "g7"
    ]
   }
  }
 },
 "best": {
  "uci": "c1d2",
  "san": "Bd2",
  "frees": [
   {
    "sq": "c3",
    "piece": "knight",
    "now_guards": [
     "e4"
    ]
   }
  ],
  "attacks": [],
  "safe": true
 }
};
export default qf3Moment;
