import "@fontsource-variable/ibm-plex-sans";
import "@fontsource/ibm-plex-mono";
import "@fontsource/ibm-plex-serif";
import { Worker } from "@react-pdf-viewer/core";
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { SharedConversationView } from "./components/SharedConversationView";
import { TooltipProvider } from "./components/ui/tooltip";
import "./index.css";

const root = document.getElementById("root");
if (!root) {
	throw new Error("Root element not found");
}

const WORKER_URL = new URL(
	"pdfjs-dist/build/pdf.worker.min.js",
	import.meta.url,
).toString();

const isSharedView = window.location.pathname.startsWith("/shared/");

ReactDOM.createRoot(root).render(
	<React.StrictMode>
		{isSharedView ? (
			<Worker workerUrl={WORKER_URL}>
				<TooltipProvider delayDuration={200}>
					<SharedConversationView />
				</TooltipProvider>
			</Worker>
		) : (
			<App />
		)}
	</React.StrictMode>,
);
