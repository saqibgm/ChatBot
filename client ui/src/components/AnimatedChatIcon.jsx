import React from 'react';

/**
 * Professional chatbot floating icon with chat bubble design
 * and a small badge accent.
 */
const AnimatedChatIcon = ({ size = 56, className = '', isOpen = false, themeColor = null }) => {
    const primaryColor = themeColor || '#000000';

    function adjustBrightness(hex, percent) {
        if (!hex || !hex.startsWith('#')) return hex;
        const num = parseInt(hex.replace('#', ''), 16);
        const amt = Math.round(2.55 * percent);
        const R = Math.min(255, Math.max(0, (num >> 16) + amt));
        const G = Math.min(255, Math.max(0, ((num >> 8) & 0x00FF) + amt));
        const B = Math.min(255, Math.max(0, (num & 0x0000FF) + amt));
        return '#' + (0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1);
    }

    const lighterColor = adjustBrightness(primaryColor, 30);

    return (
        <div
            className={`chat-icon-container ${className} ${isOpen ? 'open' : ''}`}
            style={{
                width: size,
                height: size,
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
            }}
        >
            {/* Subtle ambient glow */}
            <div style={{
                position: 'absolute',
                width: '120%',
                height: '120%',
                background: `radial-gradient(circle, ${primaryColor}30 0%, transparent 70%)`,
                borderRadius: '50%',
                filter: 'blur(10px)',
                animation: 'iconGlow 3s ease-in-out infinite',
                zIndex: 0,
            }} />

            {/* Main circular button with chat icon */}
            <div style={{
                width: '100%',
                height: '100%',
                borderRadius: '50%',
                background: `linear-gradient(135deg, ${primaryColor}, ${lighterColor})`,
                boxShadow: `0 6px 20px ${primaryColor}50`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                position: 'relative',
                zIndex: 1,
            }}>
                {/* Chat bubble SVG icon */}
                <svg width={size * 0.45} height={size * 0.45} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M20 2H4C2.9 2 2 2.9 2 4V22L6 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2Z" fill="white" />
                    <circle cx="8" cy="10" r="1.5" fill={primaryColor} />
                    <circle cx="12" cy="10" r="1.5" fill={primaryColor} />
                    <circle cx="16" cy="10" r="1.5" fill={primaryColor} />
                </svg>
            </div>

            {/* Small badge dot in bottom-right */}
            <div style={{
                position: 'absolute',
                bottom: '2px',
                right: '2px',
                width: '16px',
                height: '16px',
                borderRadius: '50%',
                backgroundColor: '#22c55e',
                border: '2px solid white',
                zIndex: 2,
                boxShadow: '0 2px 6px rgba(0,0,0,0.2)',
            }} />

            {/* Pulse ring */}
            <span style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                width: '100%',
                height: '100%',
                border: `2px solid ${primaryColor}25`,
                borderRadius: '50%',
                transform: 'translate(-50%, -50%) scale(1)',
                opacity: 0,
                animation: 'iconPulse 3s ease-out infinite',
                zIndex: 0,
            }} />

            <style>{`
                @keyframes iconGlow {
                    0%, 100% { opacity: 0.5; transform: scale(1); }
                    50% { opacity: 0.8; transform: scale(1.05); }
                }
                @keyframes iconPulse {
                    0% { transform: translate(-50%, -50%) scale(0.9); opacity: 0.4; }
                    100% { transform: translate(-50%, -50%) scale(1.5); opacity: 0; }
                }
                .chat-icon-container {
                    animation: iconBreathe 3.5s ease-in-out infinite;
                    cursor: pointer;
                    transition: transform 0.3s ease;
                }
                .chat-icon-container:hover {
                    transform: scale(1.08);
                }
                @keyframes iconBreathe {
                    0%, 100% { transform: scale(1); }
                    50% { transform: scale(1.03); }
                }
                .chat-icon-container.open {
                    animation: none;
                }
                @media (prefers-reduced-motion: reduce) {
                    .chat-icon-container,
                    .chat-icon-container span {
                        animation: none !important;
                    }
                }
            `}</style>
        </div>
    );
};

export default AnimatedChatIcon;
