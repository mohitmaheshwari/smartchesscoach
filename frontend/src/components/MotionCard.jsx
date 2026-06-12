import { motion } from "framer-motion";
import { staggerItem } from "@/lib/motion";

export function MotionCard({ children, className = "" }) {
  return (
    <motion.div
      variants={staggerItem}
      className={`rounded-lg border border-white/10 bg-white/5 backdrop-blur p-6 ${className}`}
    >
      {children}
    </motion.div>
  );
}
