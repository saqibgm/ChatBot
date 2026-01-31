import React, { useState, useRef, useEffect } from 'react';
import { Minimize2, X, Trash2, XCircle, Package, ShoppingCart, Users, ListOrdered, Send, FileText, Search } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import MessageBubble from './MessageBubble';
import AnimatedChatIcon from './AnimatedChatIcon';
import { v4 as uuidv4 } from 'uuid';
import logoImg from '../assets/logo.png';

const RASA_API_URL = 'http://127.0.0.1:5105/webhooks/rest/webhook';

// localStorage keys with appId prefix for multi-widget support
const getStorageKey = (appId, key) => `createl - chat - ${appId} -${key} `;

const ChatWindow = ({ title = "Createl Bot", appId = "General", theme = null }) => {
    // Theme override state (for "set theme {id}" chat command)
    const [themeOverride, setThemeOverride] = useState(null);
    const activeTheme = themeOverride || theme;

    // Extract theme properties with defaults
    const primaryColor = activeTheme?.primaryColor || '#000000';
    const secondaryColor = activeTheme?.secondaryColor || adjustBrightness(primaryColor, 20);
    const bgColor = activeTheme?.bgColor || '#ffffff';
    const textColor = activeTheme?.textColor || '#1f2937';
    const fontFamily = activeTheme?.fontFamily || 'Inter';
    const borderRadius = activeTheme?.borderRadius || '12';

    // Icon settings
    const botIcon = activeTheme?.botIcon || '🛒';
    const botIconColor = activeTheme?.botIconColor || primaryColor;
    const userIcon = activeTheme?.userIcon || '👤';
    const userIconColor = activeTheme?.userIconColor || '#e5e7eb';
    const sendIcon = activeTheme?.sendIcon || '➤';
    const sendIconColor = activeTheme?.sendIconColor || primaryColor;
    const attachIcon = activeTheme?.attachIcon || '📎';

    // Font size settings
    const headerFontSize = activeTheme?.headerFontSize || '16';
    const messageFontSize = activeTheme?.messageFontSize || '14';
    const buttonFontSize = activeTheme?.buttonFontSize || '13';
    const inputFontSize = activeTheme?.inputFontSize || '14';

    // Compute derived colors
    const hoverColor = adjustBrightness(primaryColor, 20);
    const shadowColor = `${primaryColor} 4D`; // 30% opacity

    // Helper function to adjust color brightness
    function adjustBrightness(hex, percent) {
        if (!hex || !hex.startsWith('#')) return hex;
        const num = parseInt(hex.replace('#', ''), 16);
        const amt = Math.round(2.55 * percent);
        const R = Math.min(255, Math.max(0, (num >> 16) + amt));
        const G = Math.min(255, Math.max(0, ((num >> 8) & 0x00FF) + amt));
        const B = Math.min(255, Math.max(0, (num & 0x0000FF) + amt));
        return '#' + (0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1);
    }

    // Persist senderId across sessions
    const [senderId] = useState(() => {
        const stored = localStorage.getItem(getStorageKey(appId, 'senderId'));
        if (stored) return stored;
        const newId = uuidv4();
        localStorage.setItem(getStorageKey(appId, 'senderId'), newId);
        return newId;
    });

    // Authentication state - always authenticated (no login required)
    const [isAuthenticated, setIsAuthenticated] = useState(true);
    const [authUser, setAuthUser] = useState('');

    // Load saved messages or use welcome message
    const [messages, setMessages] = useState(() => {
        const saved = localStorage.getItem(getStorageKey(appId, 'messages'));
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                if (Array.isArray(parsed) && parsed.length > 0) {
                    return parsed;
                }
            } catch (e) {
                console.warn('Failed to parse saved messages:', e);
            }
        }
        return [{ id: 'init', sender: 'bot', text: `Welcome to ${title}. How can I help you ? ` }];
    });

    const [showPrivacyPopup, setShowPrivacyPopup] = useState(false);

    // Debug log
    useEffect(() => {
        console.log('Privacy Popup State:', showPrivacyPopup, 'Authenticated:', isAuthenticated);
    }, [showPrivacyPopup, isAuthenticated]);

    const [showTicketFilterPopup, setShowTicketFilterPopup] = useState(false);
    const [showTicketIdPopup, setShowTicketIdPopup] = useState(false);
    const [ticketIdInput, setTicketIdInput] = useState('');
    const [searchContext, setSearchContext] = useState({ open: false, type: null });
    const [searchQuery, setSearchQuery] = useState('');
    const [lastProductId, setLastProductId] = useState('');
    const [stockPopup, setStockPopup] = useState({ open: false, productId: '' });
    const [stockQuantity, setStockQuantity] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isOpen, setIsOpen] = useState(false);
    const messagesEndRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    // Save messages to localStorage whenever they change
    useEffect(() => {
        localStorage.setItem(getStorageKey(appId, 'messages'), JSON.stringify(messages));
    }, [messages, appId]);

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Scroll to bottom when chat opens (for history reload)
    useEffect(() => {
        if (isOpen) {
            // Use instant scroll on open so user sees latest messages immediately
            setTimeout(() => {
                messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
            }, 100);
        }
    }, [isOpen]);

    // Fetch admin profile on first open
    const [adminFetched, setAdminFetched] = useState(false);

    useEffect(() => {
        const fetchAdminProfile = async () => {
            if (adminFetched || !isOpen) return;

            try {
                const response = await fetch(RASA_API_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        sender: senderId,
                        message: '/admin_me',
                        metadata: { app_id: appId }
                    }),
                });

                const data = await response.json();

                // Look for admin_me response with display_name
                for (const msg of data) {
                    if (msg.custom?.admin_me && msg.custom?.display_name) {
                        const userName = msg.custom.display_name;
                        setAuthUser(userName);
                        // Update welcome message with username
                        setMessages(prev => {
                            if (prev.length === 1 && prev[0].id === 'init') {
                                return [{ id: 'init', sender: 'bot', text: `${userName}, Welcome to ${title}. How can I help you ? ` }];
                            }
                            return prev;
                        });
                        break;
                    }
                }
                setAdminFetched(true);
            } catch (error) {
                console.error('Error fetching admin profile:', error);
                setAdminFetched(true);
            }
        };

        fetchAdminProfile();
    }, [isOpen, adminFetched, senderId, appId, title]);

    // Handle Clear History
    const handleClearHistory = () => {
        localStorage.removeItem(getStorageKey(appId, 'messages'));
        localStorage.removeItem(getStorageKey(appId, 'senderId'));
        const newId = uuidv4();
        localStorage.setItem(getStorageKey(appId, 'senderId'), newId);
        const welcomeText = authUser
            ? `${authUser}, Welcome to ${title}. How can I help you ? `
            : `Welcome to ${title}. How can I help you ? `;
        setMessages([{ id: 'init', sender: 'bot', text: welcomeText }]);
    };

    // Guard Rails: Input Validation
    const validateInput = (message) => {
        // Block profanity (basic list - expand as needed)
        const profanityList = ['damn', 'hell', 'crap', 'stupid', 'idiot'];
        const lowerMessage = message.toLowerCase();
        if (profanityList.some(word => lowerMessage.includes(word))) {
            return { valid: false, error: "Please keep the conversation professional." };
        }

        // Block PII patterns
        const ssnPattern = /\b\d{3}-\d{2}-\d{4}\b/;
        const creditCardPattern = /\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b/;

        if (ssnPattern.test(message)) {
            return { valid: false, error: "Please don't share Social Security Numbers. Contact support directly for sensitive information." };
        }

        if (creditCardPattern.test(message)) {
            return { valid: false, error: "Please don't share credit card numbers. Contact support directly for payment issues." };
        }

        // Block excessive length (500 char limit)
        if (message.length > 500) {
            return { valid: false, error: "Please keep your message under 500 characters. Break it into multiple messages if needed." };
        }

        // Block spam-like patterns (all caps, excessive punctuation)
        const capsRatio = (message.match(/[A-Z]/g) || []).length / message.length;
        if (message.length > 20 && capsRatio > 0.7) {
            return { valid: false, error: "Please don't use excessive CAPS. It's considered shouting." };
        }

        return { valid: true };
    };

    // Handle feedback (thumbs up/down) - sends to Rasa backend
    const handleFeedback = async (messageId, feedbackType) => {
        try {
            const intent = feedbackType === 'up' ? '/feedback_positive' : '/feedback_negative';
            await fetch(RASA_API_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sender: senderId,
                    message: intent,
                    metadata: { app_id: appId }
                })
            });
            console.log(`Feedback ${feedbackType} sent for message ${messageId}`);
        } catch (error) {
            console.error('Error sending feedback:', error);
        }
    };

    const handleTicketFilterSubmit = (statusId) => {
        setShowTicketFilterPopup(false);
        const payload = `/ list_tickets{ "status_id": ${statusId} } `; // Just numbers, no quotes for int
        handleButtonClick(payload); // Recursive call but now it acts as manual send
    };

    // Handle button clicks from fallback suggestions
    const handleButtonClick = async (payload) => {
        // Helper to extract JSON data from payload like /intent{"key":"value"}
        const extractPayloadData = (p, intent) => {
            if (p.startsWith(intent + '{')) {
                try {
                    const jsonStr = p.substring(intent.length);
                    return JSON.parse(jsonStr);
                } catch (e) {
                    return null;
                }
            }
            return null;
        };

        // Intercept Check Status to show popup
        if (payload === '/check_status') {
            setShowTicketIdPopup(true);
            return;
        }

        // Intercept List Tickets to show Filter popup
        // BUT prevent loop if it's the recursive call with status_id inside
        if (payload === '/list_tickets' && !payload.includes('{')) {
            setShowTicketFilterPopup(true);
            return;
        }

        // === BUTTONS THAT NEED POPUPS ===

        // Track Order - needs order ID (show popup even if has data, to confirm)
        if (payload === '/track_order' || payload.startsWith('/track_order{')) {
            const data = extractPayloadData(payload, '/track_order');
            if (data?.order_id) {
                setSearchQuery(String(data.order_id));
            }
            openSearchPopup('order');
            return;
        }

        // Search Products - needs product name/ID
        if (payload === '/search_products' || payload.startsWith('/search_products{')) {
            openSearchPopup('search_product');
            return;
        }

        // Check Stock - needs product ID
        if (payload === '/check_stock' || payload.startsWith('/check_stock{')) {
            const data = extractPayloadData(payload, '/check_stock');
            if (data?.product_id) {
                setSearchQuery(String(data.product_id));
            }
            openSearchPopup('stock_check');
            return;
        }

        // Get Invoice - auto-detects order ID on backend (no popup needed)

        // Update Stock - needs product ID + quantity (ALWAYS show popup)
        if (payload === '/update_stock' || payload.startsWith('/update_stock{')) {
            const data = extractPayloadData(payload, '/update_stock');
            if (data?.product_id) {
                setStockPopup({ open: true, productId: String(data.product_id) });
                setStockQuantity('');
            } else {
                openStockPopup();
            }
            return;
        }

        // Admin Find Customer - needs customer ID/email
        if (payload === '/admin_find_customer' || payload.startsWith('/admin_find_customer{')) {
            openSearchPopup('customer');
            return;
        }

        // Admin Get Customer - needs customer ID
        if (payload === '/admin_get_customer' || payload.startsWith('/admin_get_customer{')) {
            const data = extractPayloadData(payload, '/admin_get_customer');
            if (data?.customer_id) {
                setSearchQuery(String(data.customer_id));
            }
            openSearchPopup('admin_customer');
            return;
        }

        // Admin Customer Last Orders - needs customer ID
        if (payload === '/admin_customer_last_orders' || payload.startsWith('/admin_customer_last_orders{')) {
            const data = extractPayloadData(payload, '/admin_customer_last_orders');
            if (data?.customer_id) {
                setSearchQuery(String(data.customer_id));
            }
            openSearchPopup('customer_orders');
            return;
        }

        // Admin Find Product - needs product search
        if (payload === '/admin_find_product' || payload.startsWith('/admin_find_product{')) {
            openSearchPopup('admin_product');
            return;
        }

        // === BUTTONS THAT DON'T NEED POPUPS ===
        // /help - shows help info
        // /list_orders - lists user's orders
        // /admin_token_me - shows admin profile

        // Extract intent from payload (e.g., "/list_tickets" -> "list_tickets")
        const message = payload.startsWith('/') ? payload : `/ ${payload} `;

        // Match ticket submission to show formatted summary
        let displayText = payload;
        if (payload.startsWith('/submit_ticket_form')) {
            try {
                const jsonStr = payload.replace('/submit_ticket_form', '');
                const data = JSON.parse(jsonStr);
                displayText = `📝 Ticket Request: \n${data.title} (${data.category}) \nPriority: ${data.priority} `;
            } catch (e) {
                displayText = '📝 Submitting Ticket...';
            }
        } else if (payload.includes('status_id')) {
            // Friendly text for user
            displayText = "🔍 Filtering tickets...";
        }

        // Show user's choice
        const userMsg = { id: uuidv4(), sender: senderId, text: displayText };
        setMessages(prev => [...prev, userMsg]);
        setIsLoading(true);

        try {
            const response = await fetch(RASA_API_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sender: senderId,
                    message: message,
                    metadata: { app_id: appId }
                }),
            });

            const data = await response.json();

            if (data && data.length > 0) {
                // Process messages, merging video data and filtering empty ones
                let lastTextMessage = null;
                const processedMessages = [];

                for (const msg of data) {
                    if (msg.text) {
                        lastTextMessage = {
                            id: uuidv4(),
                            sender: 'bot',
                            text: msg.text,
                            buttons: msg.buttons,
                            chart: msg.chart || msg.custom?.chart,
                            video: msg.custom?.video,
                            ticket_form: msg.custom?.ticket_form,
                            invoice: msg.custom?.invoice ? {
                                order_id: msg.custom.order_id,
                                filename: msg.custom.filename,
                                pdf_data: msg.custom.pdf_data
                            } : null
                        };
                        processedMessages.push(lastTextMessage);
                    } else if (msg.custom?.chart && lastTextMessage) {
                        lastTextMessage.chart = msg.custom.chart;
                    } else if (msg.custom?.chart) {
                        processedMessages.push({
                            id: uuidv4(),
                            sender: 'bot',
                            text: '',
                            chart: msg.custom.chart
                        });
                    } else if (msg.custom?.video && lastTextMessage) {
                        lastTextMessage.video = msg.custom.video;
                    } else if (msg.custom?.video) {
                        processedMessages.push({
                            id: uuidv4(),
                            sender: 'bot',
                            text: '',
                            video: msg.custom.video
                        });
                    } else if (msg.custom?.ticket_form && lastTextMessage) {
                        lastTextMessage.ticket_form = msg.custom.ticket_form;
                    } else if (msg.custom?.ticket_form) {
                        processedMessages.push({
                            id: uuidv4(),
                            sender: 'bot',
                            text: '',
                            ticket_form: msg.custom.ticket_form,
                            buttons: []
                        });
                    } else if (msg.custom?.ticket_form && lastTextMessage) {
                        lastTextMessage.ticket_form = msg.custom.ticket_form;
                    } else if (msg.custom?.ticket_form) {
                        processedMessages.push({
                            id: uuidv4(),
                            sender: 'bot',
                            text: '',
                            ticket_form: msg.custom.ticket_form,
                            buttons: [] // Ensure buttons don't float weirdly
                        });
                    }
                }

                if (processedMessages.length > 0) {
                    setMessages(prev => [...prev, ...processedMessages]);
                }
            }
        } catch (error) {
            console.error("Error:", error);
            setMessages(prev => [...prev, { id: uuidv4(), sender: 'bot', text: "⚠️ Error connecting to server." }]);
        } finally {
            setIsLoading(false);
        }
    };

    const sendTextMessage = async (text) => {
        if (!text.trim()) return;

        const productMatch = text.match(/product\s*(?:id\s*)?(\d+)/i);
        if (productMatch?.[1]) {
            setLastProductId(productMatch[1]);
        }

        // Guard Rails: Validate input
        const validation = validateInput(text);
        if (!validation.valid) {
            setMessages(prev => [...prev, {
                id: uuidv4(),
                sender: 'bot',
                text: `⚠️ ${validation.error} `
            }]);
            return;
        }

        // Handle "set theme {id}" command
        const themeMatch = text.match(/^set\s+theme\s+(\d+)$/i);
        if (themeMatch) {
            const themeId = themeMatch[1];
            setMessages(prev => [...prev, { id: uuidv4(), sender: senderId, text }]);
            setIsLoading(true);
            try {
                const res = await fetch(`http://localhost:8181/admin/themes/${themeId}`);
                const data = await res.json();
                if (data.success && data.theme) {
                    const settings = data.theme.settings;
                    setThemeOverride(settings);
                    setMessages(prev => [...prev, {
                        id: uuidv4(), sender: 'bot',
                        text: `Theme changed to **${data.theme.name}** (ID: ${themeId})`
                    }]);
                } else {
                    setMessages(prev => [...prev, {
                        id: uuidv4(), sender: 'bot',
                        text: `Theme with ID ${themeId} not found.`
                    }]);
                }
            } catch (e) {
                setMessages(prev => [...prev, {
                    id: uuidv4(), sender: 'bot',
                    text: `Failed to load theme ${themeId}.`
                }]);
            }
            setIsLoading(false);
            return;
        }

        const userMsg = { id: uuidv4(), sender: senderId, text };
        setMessages(prev => [...prev, userMsg]);
        setIsLoading(true);

        try {
            const response = await fetch(RASA_API_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sender: senderId,
                    message: text,
                    metadata: { app_id: appId }
                }),
            });

            const data = await response.json();

            if (data && data.length > 0) {
                // Process messages, merging video data and filtering empty ones
                let lastTextMessage = null;
                const processedMessages = [];

                for (const msg of data) {
                    if (msg.text) {
                        // Message with text - create a proper message object
                        lastTextMessage = {
                            id: uuidv4(),
                            sender: 'bot',
                            text: msg.text,
                            buttons: msg.buttons,
                            chart: msg.chart || msg.custom?.chart,
                            video: msg.custom?.video,
                            ticket_form: msg.custom?.ticket_form,
                            invoice: msg.custom?.invoice ? {
                                order_id: msg.custom.order_id,
                                filename: msg.custom.filename,
                                pdf_data: msg.custom.pdf_data
                            } : null
                        };
                        processedMessages.push(lastTextMessage);
                    } else if (msg.custom?.chart && lastTextMessage) {
                        // Chart-only message - merge into the last text message
                        lastTextMessage.chart = msg.custom.chart;
                    } else if (msg.custom?.chart) {
                        // Standalone chart message (no previous text) - show it
                        processedMessages.push({
                            id: uuidv4(),
                            sender: 'bot',
                            text: '',
                            chart: msg.custom.chart
                        });
                    } else if (msg.custom?.video && lastTextMessage) {
                        // Video-only message - merge into the last text message
                        lastTextMessage.video = msg.custom.video;
                    } else if (msg.custom?.video) {
                        // Standalone video message (no previous text) - show it
                        processedMessages.push({
                            id: uuidv4(),
                            sender: 'bot',
                            text: '',
                            video: msg.custom.video
                        });
                    } else if (msg.custom?.ticket_form && lastTextMessage) {
                        lastTextMessage.ticket_form = msg.custom.ticket_form;
                    } else if (msg.custom?.ticket_form) {
                        processedMessages.push({
                            id: uuidv4(),
                            sender: 'bot',
                            text: '',
                            ticket_form: msg.custom.ticket_form
                        });
                    } else if (msg.image) {
                        processedMessages.push({
                            id: uuidv4(),
                            sender: 'bot',
                            text: '![image](' + msg.image + ')'
                        });
                    }
                    // Skip completely empty messages
                }

                if (processedMessages.length > 0) {
                    setMessages(prev => [...prev, ...processedMessages]);
                }
            } else {
                // Fallback with helpful suggestions
                const fallbackMessage = {
                    id: uuidv4(),
                    sender: 'bot',
                    text: "I'm not sure I understand. Here's what I can help you with:",
                    buttons: [
                        { title: "🛒 Order", payload: "/track_order" },
                        { title: "📦 Product", payload: "/search_products" },
                        { title: "👤 Customer", payload: "/admin_find_customer" }
                    ]
                };

                setMessages(prev => [...prev, fallbackMessage]);
            }

        } catch (error) {
            console.error("Error:", error);
            setMessages(prev => [...prev, { id: uuidv4(), sender: 'bot', text: "⚠️ Error connecting to server." }]);
        } finally {
            setIsLoading(false);
        }
    };

    const searchActions = [
        {
            key: 'product',
            label: 'Product',
            icon: Package,
            placeholder: 'Enter product ID (number)',
            buildMessage: (q) => `/product_details{"product_id":"${q}"}`
        },
        {
            key: 'search_product',
            label: 'Search Product',
            icon: Search,
            placeholder: 'Enter product name',
            buildMessage: (q) => `/search_products{"search_query":"${q}"}`,
            hidden: true
        },
        {
            key: 'order',
            label: 'Order',
            icon: ShoppingCart,
            placeholder: 'Enter order ID',
            buildMessage: (q) => `/track_order{"order_id":"${q}"}`
        },
        {
            key: 'customer',
            label: 'Customer',
            icon: Users,
            placeholder: 'Enter customer ID (number)',
            buildMessage: (q) => `/admin_get_customer{"customer_id":"${q}"}`
        },
        {
            key: 'invoice',
            label: 'Invoice',
            icon: FileText,
            placeholder: 'Enter order ID for invoice',
            buildMessage: (q) => `/get_invoice{"order_id":"${q}"}`
        },
        {
            key: 'stock_check',
            label: 'Stock',
            icon: Package,
            placeholder: 'Enter product ID to check stock',
            buildMessage: (q) => `/check_stock{"product_id":"${q}"}`
        },
        {
            key: 'update_stock',
            label: 'Stock',
            icon: Package,
            hidden: true
        },
        {
            key: 'admin_customer',
            label: 'Get Customer',
            icon: Users,
            placeholder: 'Enter customer ID',
            buildMessage: (q) => `/admin_get_customer{"customer_id":"${q}"}`,
            hidden: true
        },
        {
            key: 'customer_orders',
            label: 'Customer Orders',
            icon: ShoppingCart,
            placeholder: 'Enter customer ID',
            buildMessage: (q) => `/admin_customer_last_orders{"customer_id":"${q}"}`,
            hidden: true
        },
        {
            key: 'admin_product',
            label: 'Find Product',
            icon: Package,
            placeholder: 'Enter product name or ID',
            buildMessage: (q) => `/admin_find_product{"product_name":"${q}"}`,
            hidden: true
        }
    ];

    const openSearchPopup = (type) => {
        setSearchQuery('');
        setSearchContext({ open: true, type });
    };

    const openStockPopup = () => {
        setStockQuantity('');
        setStockPopup({ open: true, productId: lastProductId || '' });
    };

    const handleSearchSubmit = async (e) => {
        e.preventDefault();
        const action = searchActions.find(a => a.key === searchContext.type);
        if (!action) return;

        const query = searchQuery.trim();
        if (!query) return;

        const message = action.buildMessage ? action.buildMessage(query) : query;

        // Close popup immediately
        setSearchContext({ open: false, type: null });
        setSearchQuery('');

        // Then send the message
        await sendTextMessage(message);
    };

    const handleStockSubmit = async (e) => {
        e.preventDefault();
        const productId = stockPopup.productId.trim();
        const qty = stockQuantity.trim();
        if (!productId) {
            setMessages(prev => [...prev, { id: uuidv4(), sender: 'bot', text: '⚠️ Please provide a product ID.' }]);
            return;
        }
        if (!/^[0-9]+$/.test(qty)) {
            setMessages(prev => [...prev, { id: uuidv4(), sender: 'bot', text: '⚠️ Please enter a valid stock quantity.' }]);
            return;
        }
        // Close popup immediately
        setStockPopup({ open: false, productId: '' });
        setStockQuantity('');
        // Then send the message
        await sendTextMessage(`/update_stock{"product_id":"${productId}","stock_quantity":"${qty}"}`);
    };

    const handleTicketIdSubmit = async (e) => {
        e.preventDefault();
        if (!ticketIdInput.trim()) return;

        setShowTicketIdPopup(false);
        // Clean ID - remove "Createl-" prefix if user typed it, though backend might handle it
        // sending standard entity payload
        const payload = `/check_status{"ticket_id":"${ticketIdInput.trim()}"}`;
        handleButtonClick(payload);
        setTicketIdInput('');
    };

    return (
        <div className="fixed bottom-6 right-6 z-[9999] flex flex-col items-end" style={{ fontFamily }}>
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.9, y: 20 }}
                        className="w-[432px] h-[648px] border border-gray-200 flex flex-col overflow-hidden mb-4 relative"
                        style={{
                            backgroundColor: bgColor,
                            borderRadius: `${borderRadius}px`,
                            color: textColor,
                            boxShadow: `0 25px 50px -12px rgba(0,0,0,0.15), 0 0 0 1px rgba(0,0,0,0.05)`
                        }}
                    >
                        {/* Header */}
                        <div
                            className="px-4 py-3 flex items-center justify-between text-white"
                            style={{
                                background: `linear-gradient(135deg, ${primaryColor} 0%, ${secondaryColor} 100%)`,
                                fontSize: `${headerFontSize}px`,
                                boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
                            }}
                        >
                            <div className="flex items-center space-x-3">
                                <img src={logoImg} alt="Logo" className="h-[21px] w-auto object-contain rounded-sm bg-white" style={{ transform: 'scaleY(1.2)' }} />
                                <svg width="48" height="48" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                                    <circle cx="50" cy="50" r="46" fill="white" opacity="0.2" />
                                    <line x1="50" y1="12" x2="50" y2="22" stroke="white" strokeWidth="4" strokeLinecap="round" />
                                    <circle cx="50" cy="10" r="5" fill="white" />
                                    <rect x="22" y="30" rx="20" ry="20" width="56" height="40" fill="white" />
                                    <circle cx="38" cy="48" r="6" fill={primaryColor} />
                                    <circle cx="62" cy="48" r="6" fill={primaryColor} />
                                    <rect x="36" y="62" rx="3" ry="3" width="28" height="6" fill={primaryColor} opacity="0.3" />
                                    <rect x="30" y="70" rx="4" ry="4" width="14" height="12" fill="white" />
                                    <rect x="56" y="70" rx="4" ry="4" width="14" height="12" fill="white" />
                                </svg>
                            </div>
                            <div className="flex flex-col items-end">
                                <div className="flex space-x-1">
                                    <button
                                        onClick={handleClearHistory}
                                        className="p-2 hover:bg-white/15 rounded-lg transition-colors"
                                        title="Clear chat history"
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                    <button onClick={() => setIsOpen(false)} className="p-2 hover:bg-white/15 rounded-lg transition-colors" title="Minimize">
                                        <Minimize2 size={16} />
                                    </button>
                                </div>
                                <div className="flex items-center space-x-1.5 mt-1 mr-1">
                                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                                    <span className="text-[11px] opacity-80 font-medium">
                                        {authUser ? authUser : 'Online'}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Filter Popup */}
                        <AnimatePresence>
                            {showTicketFilterPopup && (
                                <motion.div
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    className="absolute inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-6"
                                >
                                    <motion.div
                                        initial={{ scale: 0.9, y: 20 }}
                                        animate={{ scale: 1, y: 0 }}
                                        exit={{ scale: 0.9, y: 20 }}
                                        className="bg-white rounded-lg shadow-xl w-full max-w-sm overflow-hidden"
                                    >
                                        <div className="p-4 border-b border-gray-100 flex justify-between items-center bg-gray-50">
                                            <h3 className="font-semibold text-gray-800">Filter Tickets</h3>
                                            <button
                                                onClick={() => setShowTicketFilterPopup(false)}
                                                className="text-gray-400 hover:text-gray-600 p-1"
                                            >
                                                <XCircle size={20} />
                                            </button>
                                        </div>

                                        <div className="p-4 grid grid-cols-2 gap-2 max-h-[400px] overflow-y-auto">
                                            <button onClick={() => handleTicketFilterSubmit(1)} className="p-2 text-sm text-left border rounded hover:bg-blue-50 hover:border-blue-200 text-gray-700">🆕 New</button>
                                            <button onClick={() => handleTicketFilterSubmit(2)} className="p-2 text-sm text-left border rounded hover:bg-blue-50 hover:border-blue-200 text-gray-700">⚙️ Processing</button>
                                            <button onClick={() => handleTicketFilterSubmit(4)} className="p-2 text-sm text-left border rounded hover:bg-blue-50 hover:border-blue-200 text-gray-700">⏳ Pending</button>
                                            <button onClick={() => handleTicketFilterSubmit(10)} className="p-2 text-sm text-left border rounded hover:bg-blue-50 hover:border-blue-200 text-gray-700">👍 Approved</button>
                                            <button onClick={() => handleTicketFilterSubmit(5)} className="p-2 text-sm text-left border rounded hover:bg-blue-50 hover:border-blue-200 text-gray-700">✅ Solved</button>
                                            <button onClick={() => handleTicketFilterSubmit(6)} className="p-2 text-sm text-left border rounded hover:bg-blue-50 hover:border-blue-200 text-gray-700">🔒 Closed</button>
                                        </div>

                                        <div className="p-4 bg-gray-50 border-t border-gray-100 flex justify-end">
                                            <button
                                                onClick={() => setShowTicketFilterPopup(false)}
                                                className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800"
                                            >
                                                Cancel
                                            </button>
                                        </div>
                                    </motion.div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Ticket ID Popup */}
                        <AnimatePresence>
                            {showTicketIdPopup && (
                                <motion.div
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    className="absolute inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-6"
                                >
                                    <motion.div
                                        initial={{ scale: 0.9, y: 20 }}
                                        animate={{ scale: 1, y: 0 }}
                                        exit={{ scale: 0.9, y: 20 }}
                                        className="bg-white rounded-lg shadow-xl w-full max-w-sm overflow-hidden"
                                    >
                                        <div className="p-4 border-b border-gray-100 flex justify-between items-center bg-gray-50">
                                            <h3 className="font-semibold text-gray-800">View Ticket</h3>
                                            <button
                                                onClick={() => setShowTicketIdPopup(false)}
                                                className="text-gray-400 hover:text-gray-600 p-1"
                                            >
                                                <XCircle size={20} />
                                            </button>
                                        </div>

                                        <form onSubmit={handleTicketIdSubmit} className="p-4 space-y-4">
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                                    Ticket Number <span className="text-red-500">*</span>
                                                </label>
                                                <input
                                                    type="text"
                                                    value={ticketIdInput}
                                                    onChange={(e) => setTicketIdInput(e.target.value)}
                                                    placeholder="e.g. 12345"
                                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1"
                                                    style={{ '--tw-ring-color': primaryColor }}
                                                    autoFocus
                                                />
                                            </div>

                                            <div className="flex gap-3 pt-2">
                                                <button
                                                    type="button"
                                                    onClick={() => setShowTicketIdPopup(false)}
                                                    className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                                                >
                                                    Cancel
                                                </button>
                                                <button
                                                    type="submit"
                                                    disabled={!ticketIdInput.trim()}
                                                    className="flex-1 px-4 py-2 text-sm font-medium text-white rounded-md transition-shadow shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
                                                    style={{ backgroundColor: primaryColor }}
                                                >
                                                    Show
                                                </button>
                                            </div>
                                        </form>
                                    </motion.div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Messages Area */}
                        <div className="flex-1 overflow-y-auto p-4 space-y-3" style={{ fontSize: `${messageFontSize}px`, backgroundColor: '#f8f9fb' }}>
                            {messages.map(msg => (
                                <MessageBubble
                                    key={msg.id}
                                    message={msg}
                                    onButtonClick={handleButtonClick}
                                    onFeedback={handleFeedback}
                                    themeColor={primaryColor}
                                    botIcon={<svg width="22" height="22" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="10" r="5" fill="white" /><line x1="50" y1="14" x2="50" y2="24" stroke="white" strokeWidth="4" strokeLinecap="round" /><rect x="22" y="30" rx="20" ry="20" width="56" height="40" fill="white" /><circle cx="38" cy="48" r="6" fill={primaryColor} /><circle cx="62" cy="48" r="6" fill={primaryColor} /><rect x="36" y="62" rx="3" ry="3" width="28" height="5" fill={primaryColor} opacity="0.3" /></svg>}
                                    botIconColor={botIconColor}
                                    userIcon={userIcon}
                                    userIconColor={userIconColor}
                                    buttonFontSize={buttonFontSize}
                                />
                            ))}
                            {isLoading && (
                                <div className="flex items-center space-x-1.5 ml-10 mt-1">
                                    <div className="w-2.5 h-2.5 rounded-full animate-bounce" style={{ backgroundColor: primaryColor, opacity: 0.6, animationDelay: '0s' }}></div>
                                    <div className="w-2.5 h-2.5 rounded-full animate-bounce" style={{ backgroundColor: primaryColor, opacity: 0.6, animationDelay: '0.15s' }}></div>
                                    <div className="w-2.5 h-2.5 rounded-full animate-bounce" style={{ backgroundColor: primaryColor, opacity: 0.6, animationDelay: '0.3s' }}></div>
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* Action Buttons */}
                        <div className="px-3 py-2.5 bg-white border-t border-gray-100">
                            <div className="flex justify-between gap-2">
                                {searchActions.filter(a => !a.hidden).map((action) => {
                                    const Icon = action.icon;
                                    return (
                                        <button
                                            key={action.key}
                                            type="button"
                                            onClick={() => {
                                                if (action.key === 'update_stock') {
                                                    openStockPopup();
                                                    return;
                                                }
                                                if (action.directMessage) {
                                                    sendTextMessage(action.directMessage);
                                                    return;
                                                }
                                                openSearchPopup(action.key);
                                            }}
                                            className="flex-1 flex flex-col items-center justify-center gap-1 rounded-xl py-1 px-1 transition-all hover:scale-105"
                                            style={{ backgroundColor: `${primaryColor}0D`, border: `1px solid ${primaryColor}20` }}
                                            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = `${primaryColor}1A`; e.currentTarget.style.borderColor = `${primaryColor}40`; }}
                                            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = `${primaryColor}0D`; e.currentTarget.style.borderColor = `${primaryColor}20`; }}
                                        >
                                            <Icon size={18} style={{ color: primaryColor }} />
                                            <span className="text-[10px] font-semibold leading-tight" style={{ color: primaryColor, opacity: 0.8 }}>{action.label}</span>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Text Input Area */}
                        <div className="px-4 py-3 bg-white border-t border-gray-200">
                            <form
                                onSubmit={(e) => {
                                    e.preventDefault();
                                    const input = e.target.elements.messageInput;
                                    if (input.value.trim()) {
                                        sendTextMessage(input.value.trim());
                                        input.value = '';
                                    }
                                }}
                                className="flex gap-3 items-center"
                            >
                                <input
                                    type="text"
                                    name="messageInput"
                                    placeholder="Type your message..."
                                    className="flex-1 text-gray-800 rounded-full px-5 py-3 focus:outline-none transition-all text-sm border"
                                    style={{ borderColor: `${primaryColor}30`, fontSize: `${inputFontSize}px`, backgroundColor: '#f8f9fb' }}
                                    onFocus={(e) => { e.target.style.borderColor = primaryColor; e.target.style.backgroundColor = '#ffffff'; e.target.style.boxShadow = `0 0 0 3px ${primaryColor}15`; }}
                                    onBlur={(e) => { e.target.style.borderColor = `${primaryColor}30`; e.target.style.backgroundColor = '#f8f9fb'; e.target.style.boxShadow = 'none'; }}
                                    disabled={isLoading}
                                />
                                <button
                                    type="submit"
                                    disabled={isLoading}
                                    className="p-3 rounded-full text-white transition-all disabled:opacity-50 hover:opacity-90"
                                    style={{ backgroundColor: primaryColor, boxShadow: `0 4px 12px ${primaryColor}40` }}
                                >
                                    <Send size={18} />
                                </button>
                            </form>
                        </div>

                        {/* Search Popup */}
                        <AnimatePresence>
                            {searchContext.open && (
                                <motion.div
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    className="absolute inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50"
                                >
                                    <motion.div
                                        initial={{ scale: 0.95, opacity: 0 }}
                                        animate={{ scale: 1, opacity: 1 }}
                                        exit={{ scale: 0.95, opacity: 0 }}
                                        className="w-[90%] max-w-md bg-white rounded-xl shadow-xl p-4"
                                    >
                                        <div className="flex items-center justify-between mb-3">
                                            <h3 className="text-sm font-semibold text-gray-800">
                                                {searchActions.find(a => a.key === searchContext.type)?.label} Search
                                            </h3>
                                            <button
                                                type="button"
                                                onClick={() => setSearchContext({ open: false, type: null })}
                                                className="text-gray-400 hover:text-gray-600"
                                            >
                                                <X size={18} />
                                            </button>
                                        </div>
                                        <form onSubmit={handleSearchSubmit} className="flex gap-2">
                                            <input
                                                type="text"
                                                value={searchQuery}
                                                onChange={(e) => setSearchQuery(e.target.value)}
                                                placeholder={searchActions.find(a => a.key === searchContext.type)?.placeholder}
                                                className="flex-1 bg-gray-100 text-gray-800 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 transition-all"
                                                style={{ '--tw-ring-color': `${primaryColor}80`, fontSize: `${inputFontSize}px` }}
                                                autoFocus
                                            />
                                            <button
                                                type="submit"
                                                disabled={!searchQuery.trim() || isLoading}
                                                className="px-3 py-2 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                                                style={{ backgroundColor: primaryColor }}
                                            >
                                                Search
                                            </button>
                                        </form>
                                    </motion.div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Update Stock Popup */}
                        <AnimatePresence>
                            {stockPopup.open && (
                                <motion.div
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    className="absolute inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50"
                                >
                                    <motion.div
                                        initial={{ scale: 0.95, opacity: 0 }}
                                        animate={{ scale: 1, opacity: 1 }}
                                        exit={{ scale: 0.95, opacity: 0 }}
                                        className="w-[90%] max-w-md bg-white rounded-xl shadow-xl p-4"
                                    >
                                        <div className="flex items-center justify-between mb-3">
                                            <h3 className="text-sm font-semibold text-gray-800">Update Stock</h3>
                                            <button
                                                type="button"
                                                onClick={() => setStockPopup({ open: false, productId: '' })}
                                                className="text-gray-400 hover:text-gray-600"
                                            >
                                                <X size={18} />
                                            </button>
                                        </div>
                                        <form onSubmit={handleStockSubmit} className="flex flex-col gap-2">
                                            <input
                                                type="text"
                                                value={stockPopup.productId}
                                                onChange={(e) => setStockPopup({ open: true, productId: e.target.value })}
                                                placeholder="Product ID"
                                                className="bg-gray-100 text-gray-800 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 transition-all"
                                                style={{ '--tw-ring-color': `${primaryColor}80`, fontSize: `${inputFontSize}px` }}
                                                autoFocus
                                            />
                                            <input
                                                type="text"
                                                value={stockQuantity}
                                                onChange={(e) => setStockQuantity(e.target.value)}
                                                placeholder="Stock quantity"
                                                className="bg-gray-100 text-gray-800 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 transition-all"
                                                style={{ '--tw-ring-color': `${primaryColor}80`, fontSize: `${inputFontSize}px` }}
                                            />
                                            <button
                                                type="submit"
                                                disabled={!stockQuantity.trim() || isLoading}
                                                className="px-3 py-2 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                                                style={{ backgroundColor: primaryColor }}
                                            >
                                                Update
                                            </button>
                                        </form>
                                    </motion.div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Privacy Consent Popup - Dismissible - Absolute Positioned */}
                        <AnimatePresence>
                            {showPrivacyPopup && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: 10 }}
                                    className="absolute bottom-24 left-4 right-4 p-4 bg-blue-50/95 backdrop-blur-sm border border-blue-200 rounded-lg shadow-xl z-50"
                                >
                                    <button
                                        onClick={() => {
                                            setShowPrivacyPopup(false);
                                            localStorage.setItem(getStorageKey(appId, 'privacyDismissed'), 'true');
                                        }}
                                        className="absolute top-2 right-2 p-1 text-gray-400 hover:text-gray-600 rounded-full hover:bg-black/5 transition-colors"
                                        title="Dismiss"
                                    >
                                        <X size={16} />
                                    </button>
                                    <div className="text-sm text-blue-900 pr-6 leading-snug">
                                        <p className="font-semibold mb-1">Privacy Notice</p>
                                        By chatting, you consent to the chats being recorded, used, and shared by us and our service providers according to our
                                        <div className="mt-2 flex gap-3">
                                            <a href="/privacy_notice.html" target="_blank" rel="noopener noreferrer" className="text-blue-700 underline hover:text-blue-900 font-medium">Privacy Notice</a>
                                            <a href="/cookies_policy.html" target="_blank" rel="noopener noreferrer" className="text-blue-700 underline hover:text-blue-900 font-medium">Cookies Policy</a>
                                        </div>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                    </motion.div>
                )}
            </AnimatePresence>
            {/* Animated Chat Icon Button - Show when closed */}
            {!isOpen && (
                <motion.div
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0, opacity: 0 }}
                    transition={{ type: 'spring', stiffness: 260, damping: 20 }}
                    onClick={() => setIsOpen(true)}
                    className="cursor-pointer"
                >
                    <AnimatedChatIcon size={64} themeColor={primaryColor} />
                </motion.div>
            )}
        </div >
    );
};

export default ChatWindow;
