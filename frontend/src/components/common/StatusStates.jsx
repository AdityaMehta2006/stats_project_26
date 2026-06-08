/**
 * LoadingState.jsx / ErrorState.jsx
 * ----------------------------------
 * Reusable loading and error display components.
 */

import { motion } from "framer-motion";

export function LoadingState({ message = "Crunching the numbers…", subtext = "Fetching data from the analysis engine" }) {
  return (
    <motion.div
      className="loading-container"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
    >
      <div className="loading-spinner" />
      <div className="loading-text">{message}</div>
      <div className="loading-subtext">{subtext}</div>
    </motion.div>
  );
}

export function ErrorState({ title = "Something went wrong", message, onRetry }) {
  return (
    <motion.div
      className="error-container"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <div className="error-icon">⚠️</div>
      <div className="error-title">{title}</div>
      <div className="error-message">
        {message || "Could not connect to the analysis backend. Make sure the server is running on port 8000."}
      </div>
      {onRetry && (
        <button className="retry-button" onClick={onRetry}>
          Try Again
        </button>
      )}
    </motion.div>
  );
}
