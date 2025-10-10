import { motion } from "framer-motion";

export const ThinkingBubble = () => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="p-6 animate-fade-in"
    >
      <div className="flex items-center gap-3 px-4 py-3 bg-muted/30 rounded-lg max-w-xs backdrop-blur-sm border border-border/50">
        <div className="flex gap-1.5">
          <motion.span
            className="w-2 h-2 bg-primary/70 rounded-full"
            animate={{ 
              scale: [1, 1.2, 1],
              opacity: [0.5, 1, 0.5]
            }}
            transition={{
              duration: 1.4,
              repeat: Infinity,
              ease: "easeInOut",
              delay: 0
            }}
          />
          <motion.span
            className="w-2 h-2 bg-primary/70 rounded-full"
            animate={{ 
              scale: [1, 1.2, 1],
              opacity: [0.5, 1, 0.5]
            }}
            transition={{
              duration: 1.4,
              repeat: Infinity,
              ease: "easeInOut",
              delay: 0.2
            }}
          />
          <motion.span
            className="w-2 h-2 bg-primary/70 rounded-full"
            animate={{ 
              scale: [1, 1.2, 1],
              opacity: [0.5, 1, 0.5]
            }}
            transition={{
              duration: 1.4,
              repeat: Infinity,
              ease: "easeInOut",
              delay: 0.4
            }}
          />
        </div>
        <span className="text-sm text-muted-foreground font-medium">Thinking...</span>
      </div>
    </motion.div>
  );
};
