import { motion } from "framer-motion";
import { MOTION_TIMING } from "@/lib/motion";

export function AnimatedButton({
  children,
  onClick,
  variant = "primary",
  disabled = false,
  className = "",
  ...props
}) {
  const isDesktop = typeof window !== "undefined" && window.innerWidth >= 768;

  const baseClass = {
    // btn-sweep — gradient sweep on hover (index.css, premium UX phase 2)
    primary: "btn-sweep px-6 py-3 bg-gradient-to-r from-amber-400 to-amber-500 text-black font-semibold rounded-lg",
    secondary: "px-6 py-3 border border-white/10 text-gray-400 rounded-lg",
  }[variant];

  return (
    <motion.button
      whileHover={!disabled && isDesktop ? { scale: 1.02 } : {}}
      whileTap={!disabled ? { scale: 0.98 } : {}}
      transition={{
        duration: MOTION_TIMING.micro.duration / 1000,
        ease: MOTION_TIMING.micro.easing,
      }}
      onClick={onClick}
      disabled={disabled}
      className={`${baseClass} ${className} transition-all`}
      {...props}
    >
      {children}
    </motion.button>
  );
}
