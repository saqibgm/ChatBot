import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import ChatWindow from './components/ChatWindow'

const ADMIN_API_URL = 'http://localhost:8181';

class CreatelChatWidget extends HTMLElement {
    constructor() {
        super();
        console.log("Createl Widget: Constructor called");
        this.mountPoint = null;
        this.root = null;
        this.themeData = null; // Cached theme data
    }

    connectedCallback() {
        console.log("Createl Widget: Connected callback");
        try {
            if (!this.mountPoint) {
                this.mountPoint = document.createElement('div');
                this.appendChild(this.mountPoint);
                this.root = createRoot(this.mountPoint);
                console.log("Createl Widget: Root created");
            }
            this.loadAndRender();
        } catch (e) {
            console.error("Widget Crash:", e);
        }
    }

    static get observedAttributes() {
        return ['title', 'app-id', 'theme-id'];
    }

    attributeChangedCallback(name, oldValue, newValue) {
        if (oldValue !== newValue) {
            // If theme-id changed, reload theme data
            if (name === 'theme-id') {
                this.themeData = null;
            }
            this.loadAndRender();
        }
    }

    async loadAndRender() {
        const themeIdAttr = this.getAttribute('theme-id');

        // If theme-id is a number, fetch theme from API
        if (themeIdAttr && !themeIdAttr.startsWith('#') && !isNaN(themeIdAttr)) {
            if (!this.themeData || this.themeData.id !== parseInt(themeIdAttr)) {
                try {
                    const res = await fetch(`${ADMIN_API_URL}/admin/themes/${themeIdAttr}`);
                    const data = await res.json();
                    if (data.success && data.theme) {
                        // Handle settings as either JSON string or object
                        const settings = typeof data.theme.settings === 'string'
                            ? JSON.parse(data.theme.settings)
                            : data.theme.settings;
                        this.themeData = {
                            id: data.theme.id,
                            ...settings
                        };
                        console.log("Createl Widget: Loaded theme", this.themeData);
                    }
                } catch (e) {
                    console.warn("Createl Widget: Failed to load theme", e);
                }
            }
        } else if (themeIdAttr && themeIdAttr.startsWith('#')) {
            // Direct color value (legacy support)
            this.themeData = { primaryColor: themeIdAttr };
        } else {
            this.themeData = null;
        }

        this.render();
    }

    render() {
        if (!this.root) return;

        const title = this.getAttribute('title') || 'Createl Shop';
        const appId = this.getAttribute('app-id') || 'General';

        this.root.render(
            <StrictMode>
                <ChatWindow title={title} appId={appId} theme={this.themeData} />
            </StrictMode>
        );
    }

    disconnectedCallback() {
        if (this.root) {
            this.root.unmount();
        }
    }
}

// Define the custom element
if (!customElements.get('createl-chat-widget')) {
    customElements.define('createl-chat-widget', CreatelChatWidget);
    console.log("Createl Widget: Registered <createl-chat-widget>");
}

