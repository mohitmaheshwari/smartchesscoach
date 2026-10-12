import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronLeft, ChevronRight, Sparkles, BookOpen } from "lucide-react";

const PIECES = [
  {
    key: "pawn",
    name: "PAWN",
    value: "1 pt",
    title: "How to Move the Pawn",
    tacticalPill: "Be5",
    desc: "Pawns move forward one square at a time, but have the option to move two squares on their very first move. They capture diagonally forward one square, and can promote to any piece upon reaching the 8th rank.",
    rule: "The soul of chess. Pawns dictate structure, create outposts, and can promote into queens in the endgame.",
    whiteImg: "/assets/studio/white_piece_king.jpg",
    blackImg: "/assets/studio/black_piece_king.jpg",
    symbol: "♟",
  },
  {
    key: "knight",
    name: "KNIGHT",
    value: "3 pts",
    title: "How to Move the Knight",
    tacticalPill: "Nf3",
    desc: "The knight moves in an 'L' shape: two squares in one direction and then one square perpendicular. It is the only piece on the board that can jump over other pieces.",
    rule: "Masters of closed positions and forks. A well-placed knight on an outpost square cannot be driven away.",
    whiteImg: "/assets/studio/white_piece_king.jpg",
    blackImg: "/assets/studio/black_piece_king.jpg",
    symbol: "♞",
  },
  {
    key: "bishop",
    name: "BISHOP",
    value: "3 pts",
    title: "How to Move the Bishop",
    tacticalPill: "Bc4",
    desc: "Bishops move diagonally as many unobstructed squares as they want. Each player starts with one light-squared bishop and one dark-squared bishop.",
    rule: "Snipers of open diagonals. The bishop pair working together controls immense territory across the board.",
    whiteImg: "/assets/studio/white_piece_king.jpg",
    blackImg: "/assets/studio/black_piece_king.jpg",
    symbol: "♝",
  },
  {
    key: "rook",
    name: "ROOK",
    value: "5 pts",
    title: "How to Move the Rook",
    tacticalPill: "Rd1",
    desc: "Rooks move horizontally and vertically along ranks and files as far as they want without jumping over other pieces.",
    rule: "Major piece powerhouses. Place rooks on open files and infiltrate to the 7th rank to paralyze opponent pawns.",
    whiteImg: "/assets/studio/white_piece_king.jpg",
    blackImg: "/assets/studio/black_piece_king.jpg",
    symbol: "♜",
  },
  {
    key: "queen",
    name: "QUEEN",
    value: "9 pts",
    title: "How to Move the Queen",
    tacticalPill: "Qh5",
    desc: "The queen is the most powerful piece on the chessboard. She can move any number of unobstructed squares in any direction: horizontally, vertically, or diagonally.",
    rule: "Devastating in attack, but beware bringing her out too early where she can be harassed by minor pieces.",
    whiteImg: "/assets/studio/white_piece_king.jpg",
    blackImg: "/assets/studio/black_piece_king.jpg",
    symbol: "♛",
  },
  {
    key: "king",
    name: "KING",
    value: "Priceless",
    title: "How to Move the King",
    tacticalPill: "Ke2",
    desc: "The king is the most important piece, but is one of the weakest. The king can only move one square in any direction — up, down, to the sides, and diagonally.",
    rule: "The king may never move himself into check. Castle early for king safety, then activate the king into a dominant piece in the endgame.",
    whiteImg: "/assets/studio/white_piece_king.jpg",
    blackImg: "/assets/studio/black_piece_king.jpg",
    symbol: "♚",
  },
];

export default function StudioPieceAcademy({ theme = "white", onToggleTheme }) {
  const [selectedPieceIndex, setSelectedPieceIndex] = useState(5); // default King
  const activePiece = PIECES[selectedPieceIndex];
  const isWhite = theme === "white";

  const prevPiece = () => {
    setSelectedPieceIndex((prev) => (prev === 0 ? PIECES.length - 1 : prev - 1));
  };

  const nextPiece = () => {
    setSelectedPieceIndex((prev) => (prev === PIECES.length - 1 ? 0 : prev + 1));
  };

  return (
    <div className="flex flex-col h-full rounded-3xl bg-[#16202c]/90 border border-white/10 shadow-2xl backdrop-blur-xl p-5 text-white overflow-hidden select-none">
      {/* Top Switcher: White / Black Studio Pill */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-xl bg-white/5 border border-white/10">
            <Sparkles className="w-4 h-4 text-cyan-400" />
          </div>
          <span className="text-xs font-mono uppercase tracking-wider text-slate-300 font-bold">
            Studio Academy
          </span>
        </div>

        {/* Dual Color Switcher */}
        {onToggleTheme && (
          <div className="flex items-center p-1 rounded-full bg-[#0d141e] border border-white/10 shadow-inner">
            <button
              type="button"
              onClick={() => onToggleTheme("white")}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-all ${
                isWhite
                  ? "bg-white text-slate-950 font-bold shadow-md ring-1 ring-white/50"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <span className="w-2.5 h-2.5 rounded-full bg-white border border-slate-300 shadow-sm" />
              White
            </button>
            <button
              type="button"
              onClick={() => onToggleTheme("black")}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-all ${
                !isWhite
                  ? "bg-slate-800 text-cyan-300 font-bold shadow-md ring-1 ring-cyan-500/50"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <span className="w-2.5 h-2.5 rounded-full bg-slate-900 border border-slate-600 shadow-sm" />
              Black
            </button>
          </div>
        )}
      </div>

      {/* 3D Ceramic Centerpiece with Illuminated Studio Lighting */}
      <div className="relative flex flex-col items-center justify-center my-2 py-4">
        {/* Ambient Radial Spotlight */}
        <div className="absolute inset-0 bg-radial-gradient from-cyan-500/10 via-transparent to-transparent pointer-events-none" />

        {/* 3D Image Showcase */}
        <div className="relative w-44 h-44 rounded-2xl overflow-hidden border border-white/15 shadow-[0_15px_35px_rgba(0,0,0,0.6)] bg-gradient-to-b from-[#1b2533] to-[#0f1722] group">
          <img
            src={isWhite ? activePiece.whiteImg : activePiece.blackImg}
            alt={activePiece.name}
            className="w-full h-full object-cover object-center filter contrast-105 brightness-105 group-hover:scale-105 transition-transform duration-500"
          />
          {/* Subtle Glassmorphic Gloss */}
          <div className="absolute inset-0 bg-gradient-to-t from-[#0e1724]/90 via-transparent to-white/10 pointer-events-none" />
          
          {/* Floating Tactical Pill */}
          <div className="absolute top-2.5 left-2.5 px-2 py-1 rounded-lg bg-black/50 border border-white/20 backdrop-blur-md text-[10px] font-mono font-bold text-cyan-300 shadow-lg">
            {activePiece.tacticalPill}
          </div>
        </div>

        {/* Display Typography */}
        <div className="text-center mt-3">
          <h2 className="font-serif text-3xl font-light tracking-[0.2em] text-slate-100 uppercase">
            {activePiece.name}
          </h2>
          <span className="text-[11px] font-mono text-cyan-400 font-semibold tracking-wider">
            Valuation: {activePiece.value}
          </span>
        </div>
      </div>

      {/* Piece Carousel / Horizontal Selector */}
      <div className="flex items-center justify-between gap-1.5 my-3 p-1.5 rounded-2xl bg-[#0f1722]/80 border border-white/10">
        <button
          type="button"
          onClick={prevPiece}
          className="p-1 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
          title="Previous Piece"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        <div className="flex items-center justify-center gap-1.5 flex-1 overflow-x-auto">
          {PIECES.map((piece, idx) => {
            const isSelected = idx === selectedPieceIndex;
            return (
              <button
                key={piece.key}
                type="button"
                onClick={() => setSelectedPieceIndex(idx)}
                className={`relative flex items-center justify-center w-8 h-8 rounded-xl text-base transition-all ${
                  isSelected
                    ? "bg-gradient-to-b from-cyan-500 to-blue-600 text-slate-950 font-bold shadow-[0_0_12px_rgba(56,189,248,0.5)] scale-110"
                    : "bg-white/5 hover:bg-white/10 text-slate-300 border border-white/5"
                }`}
                title={piece.name}
              >
                <span>{piece.symbol}</span>
              </button>
            );
          })}
        </div>

        <button
          type="button"
          onClick={nextPiece}
          className="p-1 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
          title="Next Piece"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* Rules & Strategy Card */}
      <div className="flex-1 mt-1 p-3.5 rounded-2xl bg-[#111924]/80 border border-white/10 shadow-inner flex flex-col justify-between overflow-y-auto">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <BookOpen className="w-3.5 h-3.5 text-cyan-400" />
            <h4 className="text-xs font-semibold text-slate-100 tracking-tight">
              {activePiece.title}
            </h4>
          </div>
          <p className="text-[11.5px] leading-relaxed text-slate-300 font-sans">
            {activePiece.desc}
          </p>
        </div>

        <div className="mt-2.5 pt-2.5 border-t border-white/10">
          <p className="text-[10.5px] italic text-slate-400 leading-snug">
            "{activePiece.rule}"
          </p>
        </div>
      </div>
    </div>
  );
}
