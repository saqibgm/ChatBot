# actions.py

import logging
import datetime
import os
import base64
from typing import Text, List, Any, Dict

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from actions.nopcommerce_service import NopCommerceService
from actions import analytics_store
from actions.config_manager import get_nopcommerce_config, set_config_value
import json

logger = logging.getLogger(__name__)

class ActionGreet(Action):
    def name(self) -> Text:
        return "action_greet"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Try to get user name from metadata (socketio) or slots
        user_name = None
        
        # Check metadata
        latest_message = tracker.latest_message
        if latest_message:
            metadata = latest_message.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
            
            if isinstance(metadata, dict):
                first = metadata.get("firstName") or metadata.get("first_name")
                last = metadata.get("lastName") or metadata.get("last_name")
                if first or last:
                    user_name = f"{first or ''} {last or ''}".strip()
                else:
                    user_name = metadata.get("username") or metadata.get("userName") or metadata.get("user_name") or metadata.get("name")

        # Check slots if not found in metadata
        if not user_name:
            user_name = tracker.get_slot("customer_name") or tracker.get_slot("nop_username")

        # Fallback: Try api/admin/me as requested
        if not user_name:
            try:
                service = get_nop_service_cached()
                # Note: This requires the bot to have admin credentials configured
                result = service.admin_get_me()
                if result.get("success") and result.get("profile"):
                     profile = result["profile"]
                     first = profile.get("firstName") or profile.get("first_name")
                     last = profile.get("lastName") or profile.get("last_name")
                     if first or last:
                         user_name = f"{first or ''} {last or ''}".strip()
                     else:
                         user_name = profile.get("username") or profile.get("userName")
            except Exception as e:
                logger.warning(f"Failed to get admin profile for greeting: {e}")

        greeting_text = "👋 **Welcome to Createl Bot!**"
        if user_name:
            greeting_text = f"👋 **Welcome to Createl Bot, {user_name}!**"
            
        message = f"{greeting_text}\n\nI can help you with:\n\n🔍 **Search Products** - Find products in our catalog\n📦 **Check Stock** - View product availability\n🛒 **Track Orders** - Check your order status\n🧾 **Get Invoice** - Download order invoices\n\nHow can I assist you today?"

        dispatcher.utter_message(text=message, buttons=[
            {"title": "🔍 Search Products", "payload": "/search_products"},
            {"title": "🛒 Track Order", "payload": "/track_order"},
            {"title": "📦 Check Stock", "payload": "/check_stock"},
            {"title": "❓ Help", "payload": "/help"}
        ])

        return []


def get_nopcommerce_service() -> NopCommerceService:
    """Get nopCommerce service instance with current config settings."""
    config = get_nopcommerce_config()
    verify_ssl = str(config.get('verify_ssl', 'true')).strip().lower() in ['true', '1', 'yes']
    return NopCommerceService(
        config['api_url'],
        config['secret_key'],
        admin_username=config.get('admin_username'),
        admin_password=config.get('admin_password'),
        verify_ssl=verify_ssl
    )



def get_analytics_context(tracker: Tracker) -> Dict[str, str]:
    """Extract app_id, user_id, and ticket_id from tracker for analytics logging."""
    # Safely get metadata
    latest_msg = tracker.latest_message
    metadata = {}
    if isinstance(latest_msg, dict):
        metadata = latest_msg.get("metadata", {})
    
    # Handle cases where metadata might be a string (JSON) or None
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except:
            metadata = {}
    elif metadata is None:
        metadata = {}

    app_id = metadata.get("app_id") if isinstance(metadata, dict) else None
    app_id = app_id or tracker.get_slot("app_id") or "General"
    
    # Get user_id from slot (set after GLPI login)
    user_id = tracker.get_slot("glpi_user_name") or tracker.get_slot("glpi_user_id")
    
    # Get ticket_id from slot if available (set during ticket operations)
    # This persists across the conversation session after a ticket is created/viewed
    ticket_id = tracker.get_slot("ticket_id") or tracker.get_slot("current_ticket_id")
    
    # Get current intent for logging purposes
    intent = tracker.latest_message.get("intent", {}).get("name", "") if tracker.latest_message else ""
    
    # Debug logging
    logger.debug(f"Analytics context - app_id: {app_id}, user_id: {user_id}, ticket_id: {ticket_id}, intent: {intent}")
    
    return {
        "app_id": app_id,
        "user_id": user_id,
        "ticket_id": str(ticket_id) if ticket_id else None
    }


# =============================================================================
# nopCommerce E-Commerce Actions
# =============================================================================

# Global nopCommerce service instance cache
_nopcommerce_service = None

def get_nop_service_cached() -> NopCommerceService:
    """Get or create nopCommerce service instance (cached for token persistence)."""
    global _nopcommerce_service
    if _nopcommerce_service is None:
        _nopcommerce_service = get_nopcommerce_service()
    return _nopcommerce_service


# --- nopCommerce Customer Login Action ---
class ActionNopCommerceLogin(Action):
    """Authenticates customer with nopCommerce using email and password."""
    
    def name(self) -> Text:
        return "action_nopcommerce_login"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("ActionNopCommerceLogin: Starting login")
        
        try:
            # Get credentials from slots
            username = tracker.get_slot("nop_username")
            password = tracker.get_slot("nop_password")
            
            if not username or not password:
                dispatcher.utter_message(
                    text="❌ Please provide both email and password.",
                    json_message={"login_error": True, "error": "Missing credentials"}
                )
                return [SlotSet("is_authenticated", False)]
            
            # Attempt login with nopCommerce
            service = get_nop_service_cached()
            result = service.login(username, password)
            
            if result["success"]:
                # Login successful
                customer_name = result.get("customer_name") or username
                display_name = customer_name

                admin_profile = service.admin_get_me()
                if admin_profile.get("success") and isinstance(admin_profile.get("profile"), dict):
                    profile = admin_profile["profile"]
                    name_candidates = [
                        profile.get("name"),
                        profile.get("fullName"),
                        profile.get("full_name"),
                        profile.get("userName"),
                        profile.get("username"),
                        profile.get("email"),
                    ]
                    first_name = profile.get("firstName") or profile.get("first_name")
                    last_name = profile.get("lastName") or profile.get("last_name")
                    if first_name or last_name:
                        name_candidates.insert(0, f"{first_name or ''} {last_name or ''}".strip())
                    display_name = next((n for n in name_candidates if n), display_name)
                
                # Log for analytics
                sender_id = tracker.sender_id
                app_id = tracker.get_slot("app_id") or "ECommerce"
                analytics_store.log_conversation_start(sender_id, app_id, user_id=customer_name)
                
                dispatcher.utter_message(
                    text=f"""👋 **Welcome, {customer_name}!** You're now logged in.

I can help you with:

🔍 **Search Products** - Find products in our catalog
📦 **Check Stock** - View product availability
🛒 **Track Orders** - Check your order status
🧾 **Get Invoice** - Download order invoices

What would you like to do?""",
                    buttons=[
                        {"title": "🔍 Search Products", "payload": "/search_products"},
                        {"title": "🛒 Track Order", "payload": "/track_order"},
                        {"title": "📦 Check Stock", "payload": "/check_stock"}
                    ]
                )
                
                # Send login status as separate custom payload
                dispatcher.utter_message(
                    json_message={
                        "login_success": True,
                        "customer_name": customer_name,
                        "display_name": display_name,
                        "customer_id": result.get("customer_id")
                    }
                )
                
                logger.info(f"nopCommerce login successful for: {username}")
                
                return [
                    SlotSet("is_authenticated", True),
                    SlotSet("access_token", result["access_token"]),
                    SlotSet("customer_id", result.get("customer_id")),
                    SlotSet("customer_name", customer_name),
                    SlotSet("nop_password", None)  # Clear password from slot
                ]
            else:
                # Login failed
                error_msg = result.get("error", "Invalid credentials")
                logger.warning(f"nopCommerce login failed for {username}: {error_msg}")
                
                dispatcher.utter_message(
                    text=f"❌ Login failed: {error_msg}",
                    json_message={"login_error": True, "error": error_msg}
                )
                
                return [
                    SlotSet("is_authenticated", False),
                    SlotSet("nop_password", None)
                ]
                
        except Exception as e:
            logger.error(f"Error in ActionNopCommerceLogin: {e}")
            dispatcher.utter_message(
                text="❌ An error occurred during login. Please try again.",
                json_message={"login_error": True, "error": str(e)}
            )
            return [SlotSet("is_authenticated", False)]


# --- Search Products Action ---
class ActionSearchProducts(Action):
    """Search for products in nopCommerce catalog."""
    
    def name(self) -> Text:
        return "action_search_products"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("ActionSearchProducts: Starting product search")
        
        # Get search query from slot or latest message
        search_query = tracker.get_slot("search_query")
        
        # Also try to extract from message text
        if not search_query:
            latest_msg = tracker.latest_message
            if isinstance(latest_msg, dict):
                # Try entities first
                for entity in latest_msg.get("entities", []):
                    if entity.get("entity") in ("product_name", "search_query"):
                        search_query = entity.get("value")
                        break
                
                # Fallback to extracting from text after intent
                if not search_query:
                    text = latest_msg.get("text", "")
                    # Remove common prefixes
                    for prefix in ["search for", "find", "show me", "looking for", "search"]:
                        if text.lower().startswith(prefix):
                            search_query = text[len(prefix):].strip()
                            break
        
        if not search_query:
            dispatcher.utter_message(
                text="🔍 What product are you looking for?",
                buttons=[
                    {"title": "Browse All", "payload": "/search_products{\"search_query\": \"\"}"}
                ]
            )
            return []
        
        service = get_nop_service_cached()
        result = service.search_products(query=search_query, limit=10)
        logger.info(f"ActionSearchProducts: search result success={result['success']}, products={len(result.get('products', []))}, error={result.get('error')}")

        if result["success"] and result["products"]:
            products = result["products"]

            message = f"**🔍 Search Results for '{search_query}'** ({len(products)} found)\n\n"
            message += "| Product | Price | Stock |\n"
            message += "| :--- | :--- | :--- |\n"

            for p in products[:10]:
                name = p.get("name", "Unknown")[:30]
                price = p.get("price", 0)
                stock = "✅ In Stock" if p.get("in_stock") else "❌ Out of Stock"
                product_id = p.get("id")

                message += f"| **{name}** (ID: {product_id}) | ${price:.2f} | {stock} |\n"

            dispatcher.utter_message(
                text=message,
                buttons=[
                    {"title": "📦 Check Stock", "payload": "/check_stock"},
                    {"title": "🔍 Search Again", "payload": "/search_products"}
                ]
            )

            return [SlotSet("search_query", search_query)]
        elif not result["success"]:
            error_detail = result.get("error", "Unknown error")
            logger.error(f"ActionSearchProducts: API error for query '{search_query}': {error_detail}")
            dispatcher.utter_message(
                text=f"❌ Could not search products. Error: {error_detail}",
                buttons=[
                    {"title": "🔍 Try Again", "payload": "/search_products"}
                ]
            )
            return [SlotSet("search_query", None)]
        else:
            dispatcher.utter_message(
                text=f"❌ No products found matching '**{search_query}**'. Try a different search term.",
                buttons=[
                    {"title": "🔍 Try Again", "payload": "/search_products"}
                ]
            )
            return [SlotSet("search_query", None)]


# --- Get Product Details Action ---
class ActionGetProductDetails(Action):
    """Get detailed information about a specific product."""
    
    def name(self) -> Text:
        return "action_get_product_details"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("ActionGetProductDetails: Getting product details")
        
        # Get product ID from slot or entities
        product_id = tracker.get_slot("product_id")
        
        if not product_id:
            for entity in tracker.latest_message.get("entities", []):
                if entity.get("entity") == "product_id":
                    product_id = entity.get("value")
                    break
        
        if not product_id:
            dispatcher.utter_message(text="Please provide a **Product ID** (e.g., 123).")
            return []
        
        try:
            product_id = int(str(product_id).strip())
        except ValueError:
            dispatcher.utter_message(text="❌ Invalid product ID. Please provide a number.")
            return []
        
        service = get_nop_service_cached()
        result = service.get_product_details(product_id)
        
        if result["success"]:
            p = result["product"]
            
            # Build detailed product info
            stock_status = "✅ In Stock" if p.get("in_stock") else "❌ Out of Stock"
            stock_qty = p.get("stock_quantity", 0)
            
            message = f"**📦 Product Details: {p.get('name')}**\n\n"
            message += "| Property | Value |\n"
            message += "| :--- | :--- |\n"
            message += f"| **SKU** | {p.get('sku', 'N/A')} |\n"
            message += f"| **Price** | ${p.get('price', 0):.2f} |\n"

            if p.get("old_price"):
                message += f"| **Was** | ~~${p.get('old_price'):.2f}~~ |\n"

            # Show additional price fields if available
            if p.get("min_price"):
                message += f"| **Min Price** | ${p.get('min_price'):.2f} |\n"
            if p.get("price_a"):
                message += f"| **Price A** | ${p.get('price_a'):.2f} |\n"
            if p.get("price_b"):
                message += f"| **Price B** | ${p.get('price_b'):.2f} |\n"
            if p.get("price_c"):
                message += f"| **Price C** | ${p.get('price_c'):.2f} |\n"

            message += f"| **Stock** | {stock_status} ({stock_qty} units) |\n"
            
            if p.get("short_description"):
                message += f"\n📝 **Description:**\n{p.get('short_description')}\n"
            
            dispatcher.utter_message(
                text=message,
                buttons=[
                    {"title": "📦 Update Stock", "payload": f"/update_stock{{\"product_id\": \"{product_id}\"}}"},
                    {"title": "🔍 Search Products", "payload": "/search_products"}
                ]
            )
            
            return [SlotSet("product_id", str(product_id))]
        else:
            dispatcher.utter_message(text=f"❌ {result.get('error', 'Product not found.')}")
            return []


# --- Check Product Stock Action ---
class ActionCheckStock(Action):
    """Check stock availability for a product."""
    
    def name(self) -> Text:
        return "action_check_stock"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("ActionCheckStock: Checking product stock")
        
        # Get product ID
        product_id = tracker.get_slot("product_id")
        
        if not product_id:
            for entity in tracker.latest_message.get("entities", []):
                if entity.get("entity") == "product_id":
                    product_id = entity.get("value")
                    break
        
        if not product_id:
            dispatcher.utter_message(
                text="Please provide a **Product ID** to check stock (e.g., 123).",
                buttons=[
                    {"title": "🔍 Search Products First", "payload": "/search_products"}
                ]
            )
            return []
        
        try:
            product_id = int(str(product_id).strip())
        except ValueError:
            dispatcher.utter_message(text="❌ Invalid product ID.")
            return []
        
        service = get_nop_service_cached()
        result = service.get_product_stock(product_id)
        
        if result["success"]:
            stock_qty = result.get("stock_quantity", 0)
            product_name = result.get("product_name", f"Product {product_id}")
            in_stock = result.get("in_stock", False)
            
            if in_stock:
                status_icon = "✅"
                status_text = f"**In Stock** - {stock_qty} units available"
            else:
                status_icon = "❌"
                status_text = "**Out of Stock**"
            
            message = f"{status_icon} **{product_name}** (ID: {product_id})\n\n"
            message += f"📦 Stock Status: {status_text}\n"
            
            if result.get("sku"):
                message += f"🏷️ SKU: {result.get('sku')}"
            
            dispatcher.utter_message(
                text=message,
                buttons=[
                    {"title": "📦 Update Stock", "payload": f"/update_stock{{\"product_id\": \"{product_id}\"}}"},
                    {"title": "🔍 Check Another", "payload": "/check_stock"}
                ]
            )
            
            return [SlotSet("product_id", str(product_id))]
        else:
            dispatcher.utter_message(text=f"❌ {result.get('error', 'Failed to check stock.')}")
            return []


# --- Update Product Stock Action ---
class ActionUpdateStock(Action):
    """Update stock quantity for a product (admin only)."""
    
    def name(self) -> Text:
        return "action_update_stock"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("ActionUpdateStock: Updating product stock")
        
        # Get product ID and quantity
        product_id = tracker.get_slot("product_id")
        stock_quantity = tracker.get_slot("stock_quantity")
        
        # Try to extract from entities
        for entity in tracker.latest_message.get("entities", []):
            if entity.get("entity") == "product_id" and not product_id:
                product_id = entity.get("value")
            if entity.get("entity") == "stock_quantity" and not stock_quantity:
                stock_quantity = entity.get("value")
        
        if not product_id:
            dispatcher.utter_message(text="Please provide the **Product ID** to update.")
            return []
        
        if stock_quantity is None:
            dispatcher.utter_message(
                text=f"What should be the new stock quantity for Product **{product_id}**?",
                buttons=[
                    {"title": "Set to 0", "payload": f"/update_stock{{\"product_id\": \"{product_id}\", \"stock_quantity\": \"0\"}}"},
                    {"title": "Set to 10", "payload": f"/update_stock{{\"product_id\": \"{product_id}\", \"stock_quantity\": \"10\"}}"},
                    {"title": "Set to 50", "payload": f"/update_stock{{\"product_id\": \"{product_id}\", \"stock_quantity\": \"50\"}}"},
                ]
            )
            return [SlotSet("product_id", str(product_id))]
        
        try:
            product_id = int(str(product_id).strip())
            stock_quantity = int(str(stock_quantity).strip())
        except ValueError:
            dispatcher.utter_message(text="❌ Invalid product ID or quantity.")
            return []
        
        service = get_nop_service_cached()
        result = service.update_product_stock(product_id, stock_quantity)
        
        if result["success"]:
            dispatcher.utter_message(
                text=f"✅ Stock updated! Product **{product_id}** now has **{stock_quantity}** units.",
                buttons=[
                    {"title": "📦 Check Stock", "payload": f"/check_stock{{\"product_id\": \"{product_id}\"}}"},
                    {"title": "🔍 Search Products", "payload": "/search_products"}
                ]
            )
            return [SlotSet("stock_quantity", None)]
        else:
            dispatcher.utter_message(text=f"❌ {result.get('error', 'Failed to update stock.')}")
            return []


# --- Track Order Action ---
class ActionTrackOrder(Action):
    """Track an order status."""
    
    def name(self) -> Text:
        return "action_track_order"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("ActionTrackOrder: Tracking order")
        
        # Get order ID
        order_id = tracker.get_slot("order_id")
        
        if not order_id:
            for entity in tracker.latest_message.get("entities", []):
                if entity.get("entity") == "order_id":
                    order_id = entity.get("value")
                    break
        
        if not order_id:
            dispatcher.utter_message(
                text="Please provide your **Order ID** (e.g., 10001).",
                buttons=[
                    {"title": "📋 View My Orders", "payload": "/list_orders"}
                ]
            )
            return []
        
        try:
            order_id = int(str(order_id).replace("#", "").strip())
        except ValueError:
            dispatcher.utter_message(text="❌ Invalid order ID. Please provide a number.")
            return []
        
        service = get_nop_service_cached()
        result = service.track_order(order_id)
        
        if result["success"]:
            t = result["tracking"]
            
            # Status emoji mapping
            status_emoji = {
                "Pending": "⏳",
                "Processing": "🔄",
                "Complete": "✅",
                "Cancelled": "❌",
                "Shipped": "🚚",
                "Delivered": "📦"
            }
            
            status = t.get("status", "Unknown")
            emoji = status_emoji.get(status, "📋")
            
            message = f"**{emoji} Order #{t.get('order_number', order_id)} Status**\n\n"
            message += "| Property | Value |\n"
            message += "| :--- | :--- |\n"
            message += f"| **Status** | {status} |\n"
            message += f"| **Payment** | {t.get('payment_status', 'N/A')} |\n"
            message += f"| **Shipping** | {t.get('shipping_status', 'N/A')} |\n"
            message += f"| **Total** | ${t.get('total', 0):.2f} |\n"
            message += f"| **Product Types** | {t.get('items_count', 0)} products |\n"
            message += f"| **Total Items** | {t.get('total_items', 0)} items |\n"
            
            if t.get("created_on"):
                message += f"| **Ordered On** | {t.get('created_on')[:10]} |\n"
            
            message += f"\n💬 {t.get('message', '')}"
            
            dispatcher.utter_message(
                text=message,
                buttons=[
                    {"title": "🧾 Get Invoice", "payload": f"/get_invoice{{\"order_id\": \"{order_id}\"}}"},
                    {"title": "🔍 Track Another", "payload": "/track_order"}
                ]
            )
            
            return [SlotSet("order_id", str(order_id))]
        else:
            dispatcher.utter_message(text=f"❌ {result.get('error', 'Order not found.')}")
            return []


# --- Get Order Invoice Action ---
class ActionGetInvoice(Action):
    """Get PDF invoice for an order."""
    
    def name(self) -> Text:
        return "action_get_invoice"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("ActionGetInvoice: Getting order invoice")

        # Get order ID from entities first (highest priority)
        order_id = None
        for entity in tracker.latest_message.get("entities", []):
            if entity.get("entity") == "order_id":
                order_id = entity.get("value")
                break

        # If not in entities, try slot
        if not order_id:
            order_id = tracker.get_slot("order_id")

        # If still no order_id, try to get the most recent order for the customer
        if not order_id:
            customer_id = tracker.get_slot("customer_id")
            if customer_id:
                logger.info(f"No order_id provided, fetching most recent order for customer {customer_id}")
                service = get_nop_service_cached()
                orders_result = service.get_customer_orders(customer_id=customer_id, limit=1)

                if orders_result.get("success") and orders_result.get("orders"):
                    order_id = orders_result["orders"][0].get("id")
                    logger.info(f"Found most recent order: {order_id}")

        # If still no order_id, prompt user
        if not order_id:
            dispatcher.utter_message(
                text="📋 Please track an order first, then you can get the invoice.",
                buttons=[
                    {"title": "🛒 Track Order", "payload": "/track_order"},
                    {"title": "📋 View My Orders", "payload": "/list_orders"}
                ]
            )
            return []
        
        try:
            order_id = int(str(order_id).replace("#", "").strip())
            logger.info(f"Generating invoice for order: {order_id}")
        except ValueError:
            dispatcher.utter_message(text="❌ Invalid order ID.")
            return []

        service = get_nop_service_cached()
        result = service.get_order_invoice_pdf(order_id)
        
        if result["success"]:
            # Save PDF locally
            filename = result.get("filename") or f"invoice_order_{order_id}.pdf"
            invoices_dir = "invoices"
            if not os.path.exists(invoices_dir):
                os.makedirs(invoices_dir)
            
            file_path = os.path.join(invoices_dir, filename)
            abs_path = os.path.abspath(file_path)
            
            try:
                pdf_data_b64 = result.get("pdf_data", "")
                if pdf_data_b64:
                    pdf_data = base64.b64decode(pdf_data_b64)
                    with open(file_path, "wb") as f:
                        f.write(pdf_data)
                
                # Use local admin server link for download
                # TODO: Retrieve base URL from config if not localhost
                base_url = "http://localhost:8181" 
                download_link = f"{base_url}/invoices/{filename}"
                
                # Send response with file path and link
                dispatcher.utter_message(
                    text=f"🔗 [Download Invoice #{order_id}]({download_link})",
                    json_message={
                        "invoice": True,
                        "order_id": order_id,
                        "filename": filename,
                        "file_path": abs_path,
                        "pdf_data": pdf_data_b64
                    }
                )
            except Exception as e:
                logger.error(f"Failed to save invoice: {e}")
                dispatcher.utter_message(
                    text=f"🧾 **Invoice for Order #{order_id}** is ready for download (failed to save locally).",
                    json_message={
                        "invoice": True,
                        "order_id": order_id,
                        "filename": filename, 
                        "pdf_data": result.get("pdf_data")
                    }
                )
            
            return [SlotSet("order_id", str(order_id))]
        else:
            # Fallback: show order details if PDF not available
            dispatcher.utter_message(
                text=f"❌ {result.get('error', 'Failed to generate invoice.')} You can still track the order for details.",
                buttons=[
                    {"title": "🛒 Track Order", "payload": f"/track_order{{\"order_id\": \"{order_id}\"}}"}
                ]
            )
            return []


# --- Update Order Status Action ---
class ActionUpdateOrderStatus(Action):
    """Update the status of an order (admin only)."""
    
    def name(self) -> Text:
        return "action_update_order_status"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("ActionUpdateOrderStatus: Updating order status")
        
        # Get order ID and new status
        order_id = tracker.get_slot("order_id")
        new_status = tracker.get_slot("order_status")
        
        # Try to extract from entities
        for entity in tracker.latest_message.get("entities", []):
            if entity.get("entity") == "order_id" and not order_id:
                order_id = entity.get("value")
            if entity.get("entity") == "order_status" and not new_status:
                new_status = entity.get("value")
        
        if not order_id:
            dispatcher.utter_message(text="Please provide the **Order ID** to update.")
            return []
        
        if not new_status:
            dispatcher.utter_message(
                text=f"What should be the new status for Order **#{order_id}**?",
                buttons=[
                    {"title": "Processing", "payload": f"/update_order_status{{\"order_id\": \"{order_id}\", \"order_status\": \"Processing\"}}"},
                    {"title": "Complete", "payload": f"/update_order_status{{\"order_id\": \"{order_id}\", \"order_status\": \"Complete\"}}"},
                    {"title": "Cancelled", "payload": f"/update_order_status{{\"order_id\": \"{order_id}\", \"order_status\": \"Cancelled\"}}"},
                ]
            )
            return [SlotSet("order_id", str(order_id))]
        
        try:
            order_id = int(str(order_id).replace("#", "").strip())
        except ValueError:
            dispatcher.utter_message(text="❌ Invalid order ID.")
            return []
        
        service = get_nop_service_cached()
        result = service.update_order_status(order_id, new_status)
        
        if result["success"]:
            dispatcher.utter_message(
                text=f"✅ Order **#{order_id}** status updated to **{result.get('new_status')}**.",
                buttons=[
                    {"title": "🛒 View Order", "payload": f"/track_order{{\"order_id\": \"{order_id}\"}}"},
                    {"title": "📋 View All Orders", "payload": "/list_orders"}
                ]
            )
            return [SlotSet("order_status", None)]
        else:
            dispatcher.utter_message(text=f"❌ {result.get('error', 'Failed to update order status.')}")
            return []


# --- List Customer Orders Action ---
class ActionListOrders(Action):
    """List orders for the current customer."""
    
    def name(self) -> Text:
        return "action_list_orders"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("ActionListOrders: Listing customer orders")
        
        customer_id = tracker.get_slot("customer_id")
        
        service = get_nop_service_cached()
        result = service.get_customer_orders(customer_id=customer_id, limit=10)
        
        if result["success"] and result["orders"]:
            orders = result["orders"]

            message = f"**📋 Your Orders** ({len(orders)} found)\n\n"
            message += "| Order # | Status | Total | Date |\n"
            message += "| :--- | :--- | :--- | :--- |\n"

            # Track the most recent order_id for invoice generation
            most_recent_order_id = None

            for o in orders[:10]:
                order_id = o.get("id")
                status = o.get("status", "Unknown")
                total = o.get("total", 0)
                date = o.get("created_on", "")[:10] if o.get("created_on") else "N/A"

                # Save the first (most recent) order ID
                if most_recent_order_id is None:
                    most_recent_order_id = order_id

                message += f"| **#{order_id}** | {status} | ${total:.2f} | {date} |\n"

            dispatcher.utter_message(
                text=message,
                buttons=[
                    {"title": "🛒 Track Order", "payload": "/track_order"},
                    {"title": "🧾 Get Invoice", "payload": "/get_invoice"}
                ]
            )

            # Set the most recent order_id to slot so "Get Invoice" can use it
            return [SlotSet("order_id", str(most_recent_order_id) if most_recent_order_id else None)]
        else:
            dispatcher.utter_message(
                text="📋 You don't have any orders yet.",
                buttons=[
                    {"title": "🔍 Browse Products", "payload": "/search_products"}
                ]
            )

        return []


# --- Admin: Find Product by Identifier ---
class ActionAdminFindProduct(Action):
    """Find product by identifier (SKU or ID) using Admin API."""

    def name(self) -> Text:
        return "action_admin_find_product"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("ActionAdminFindProduct: Finding product by identifier")

        identifier = tracker.get_slot("product_identifier")
        if not identifier:
            for entity in tracker.latest_message.get("entities", []):
                if entity.get("entity") == "product_identifier":
                    identifier = entity.get("value")
                    break

        if not identifier:
            dispatcher.utter_message(text="Please provide a **Product identifier** (SKU or ID).")
            return []

        service = get_nop_service_cached()
        result = service.admin_find_product(str(identifier).strip())

        if result["success"]:
            p = result["product"]
            stock_status = "✅ In Stock" if p.get("in_stock") else "❌ Out of Stock"
            stock_qty = p.get("stock_quantity", 0)

            message = f"**📦 Product Found: {p.get('name')}**\n\n"
            message += "| Property | Value |\n"
            message += "| :--- | :--- |\n"
            message += f"| **ID** | {p.get('id')} |\n"
            message += f"| **SKU** | {p.get('sku', 'N/A')} |\n"
            message += f"| **Price** | ${p.get('price', 0):.2f} |\n"

            # Show additional price fields if available
            if p.get("min_price"):
                message += f"| **Min Price** | ${p.get('min_price'):.2f} |\n"
            if p.get("price_a"):
                message += f"| **Price A** | ${p.get('price_a'):.2f} |\n"
            if p.get("price_b"):
                message += f"| **Price B** | ${p.get('price_b'):.2f} |\n"
            if p.get("price_c"):
                message += f"| **Price C** | ${p.get('price_c'):.2f} |\n"

            message += f"| **Stock** | {stock_status} ({stock_qty} units) |\n"

            dispatcher.utter_message(
                text=message,
                buttons=[
                    {"title": "📦 Check Stock", "payload": f"/check_stock{{\"product_id\": \"{p.get('id')}\"}}"},
                    {"title": "📦 Update Stock", "payload": f"/update_stock{{\"product_id\": \"{p.get('id')}\"}}"}
                ]
            )
            return [SlotSet("product_id", str(p.get("id"))), SlotSet("product_identifier", str(identifier))]

        dispatcher.utter_message(text=f"❌ {result.get('error', 'Product not found.')}")
        return []


# --- Admin: Find Customer ---
class ActionAdminFindCustomer(Action):
    """Find customers by query using Admin API."""

    def name(self) -> Text:
        return "action_admin_find_customer"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("ActionAdminFindCustomer: Finding customer")

        query = tracker.get_slot("customer_query")
        if not query:
            for entity in tracker.latest_message.get("entities", []):
                if entity.get("entity") == "customer_query":
                    query = entity.get("value")
                    break

        if not query:
            dispatcher.utter_message(text="Please provide a **customer name, email, or ID** to search.")
            return []

        service = get_nop_service_cached()
        result = service.admin_find_customer(str(query).strip())

        if result["success"] and result.get("customers"):
            customers = result["customers"]
            message = f"**👤 Customers Found** ({len(customers)} results)\n\n"
            message += "| ID | Name | Email |\n"
            message += "| :--- | :--- | :--- |\n"
            for c in customers[:10]:
                name = c.get("full_name") or c.get("first_name") or c.get("email") or "Unknown"
                message += f"| **{c.get('id')}** | {name} | {c.get('email', 'N/A')} |\n"
            dispatcher.utter_message(
                text=message,
                buttons=[
                    {"title": "👤 Get Customer", "payload": "/admin_get_customer"},
                    {"title": "🧾 Last Orders", "payload": "/admin_customer_last_orders"},
                    {"title": "🛡️ Admin Profile", "payload": "/admin_token_me"}
                ]
            )
            return [SlotSet("customer_query", str(query))]

        dispatcher.utter_message(text=f"❌ {result.get('error', 'No customers found.')}")
        return []


# --- Admin: Get Customer ---
class ActionAdminGetCustomer(Action):
    """Get customer by ID using Admin API."""

    def name(self) -> Text:
        return "action_admin_get_customer"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("ActionAdminGetCustomer: Getting customer by ID")

        customer_id = tracker.get_slot("customer_id")
        if not customer_id:
            for entity in tracker.latest_message.get("entities", []):
                if entity.get("entity") == "customer_id":
                    customer_id = entity.get("value")
                    break

        if not customer_id:
            dispatcher.utter_message(text="Please provide a **Customer ID**.")
            return []

        try:
            customer_id = int(str(customer_id).strip())
        except ValueError:
            dispatcher.utter_message(text="❌ Invalid customer ID. Please provide a number.")
            return []

        service = get_nop_service_cached()
        result = service.admin_get_customer(customer_id)

        if result["success"]:
            c = result["customer"]
            message = f"**👤 Customer #{c.get('id')}**\n\n"
            message += "| Property | Value |\n"
            message += "| :--- | :--- |\n"
            message += f"| **Name** | {c.get('full_name') or 'N/A'} |\n"
            message += f"| **Email** | {c.get('email') or 'N/A'} |\n"
            message += f"| **Username** | {c.get('username') or 'N/A'} |\n"
            message += f"| **Phone** | {c.get('phone') or 'N/A'} |\n"
            dispatcher.utter_message(
                text=message,
                buttons=[
                    {"title": "👤 Customer Details", "payload": f"/admin_get_customer_details{{\"customer_id\": \"{customer_id}\"}}"},
                    {"title": "🧾 Last Orders", "payload": f"/admin_customer_last_orders{{\"customer_query\": \"{customer_id}\"}}"}
                ]
            )
            return [SlotSet("customer_id", str(customer_id))]

        dispatcher.utter_message(text=f"❌ {result.get('error', 'Customer not found.')}")
        return []


# --- Admin: Get Customer Details ---
class ActionAdminGetCustomerDetails(Action):
    """Get customer details by ID using Admin API."""

    def name(self) -> Text:
        return "action_admin_get_customer_details"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("ActionAdminGetCustomerDetails: Getting customer details")

        customer_id = tracker.get_slot("customer_id")
        if not customer_id:
            for entity in tracker.latest_message.get("entities", []):
                if entity.get("entity") == "customer_id":
                    customer_id = entity.get("value")
                    break

        if not customer_id:
            dispatcher.utter_message(text="Please provide a **Customer ID**.")
            return []

        try:
            customer_id = int(str(customer_id).strip())
        except ValueError:
            dispatcher.utter_message(text="❌ Invalid customer ID. Please provide a number.")
            return []

        service = get_nop_service_cached()
        result = service.admin_get_customer_details(customer_id)

        if result["success"]:
            c = result["customer"]
            message = f"**👤 Customer Details #{c.get('id')}**\n\n"
            message += "| Property | Value |\n"
            message += "| :--- | :--- |\n"
            message += f"| **Name** | {c.get('full_name') or 'N/A'} |\n"
            message += f"| **Email** | {c.get('email') or 'N/A'} |\n"
            message += f"| **Username** | {c.get('username') or 'N/A'} |\n"
            message += f"| **Phone** | {c.get('phone') or 'N/A'} |\n"
            message += f"| **Active** | {str(c.get('is_active', 'N/A'))} |\n"
            dispatcher.utter_message(
                text=message,
                buttons=[
                    {"title": "🧾 Last Orders", "payload": f"/admin_customer_last_orders{{\"customer_query\": \"{customer_id}\"}}"}
                ]
            )
            return [SlotSet("customer_id", str(customer_id))]

        dispatcher.utter_message(text=f"❌ {result.get('error', 'Customer details not found.')}")
        return []


# --- Admin: Customer Last Orders ---
class ActionAdminCustomerLastOrders(Action):
    """Get customer's last orders using Admin API."""

    def name(self) -> Text:
        return "action_admin_customer_last_orders"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("ActionAdminCustomerLastOrders: Getting customer last orders")

        query = tracker.get_slot("customer_query")
        limit = tracker.get_slot("order_limit")
        customer_id = tracker.get_slot("customer_id")

        for entity in tracker.latest_message.get("entities", []):
            if entity.get("entity") == "customer_query" and not query:
                query = entity.get("value")
            if entity.get("entity") == "order_limit" and not limit:
                limit = entity.get("value")

        if not query:
            if customer_id:
                query = customer_id
            else:
                dispatcher.utter_message(text="Please provide a **customer ID or email** to get recent orders.")
                return []

        try:
            limit_val = int(str(limit).strip()) if limit else 5
        except ValueError:
            limit_val = 5

        service = get_nop_service_cached()
        result = service.admin_get_customer_last_orders(str(query).strip(), limit=limit_val)

        if result["success"] and result.get("orders"):
            orders = result["orders"]
            message = f"**🧾 Last {min(limit_val, len(orders))} Orders for {query}**\n\n"
            message += "| Order # | Status | Total | Date |\n"
            message += "| :--- | :--- | :--- | :--- |\n"
            for o in orders[:limit_val]:
                order_id = o.get("id")
                status = o.get("status", "Unknown")
                total = o.get("total", 0)
                date = o.get("created_on", "")[:10] if o.get("created_on") else "N/A"
                message += f"| **#{order_id}** | {status} | ${total:.2f} | {date} |\n"
            dispatcher.utter_message(
                text=message,
                buttons=[
                    {"title": "🛒 Track Order", "payload": "/track_order"},
                    {"title": "👤 Find Customer", "payload": "/admin_find_customer"}
                ]
            )
            return [SlotSet("customer_query", str(query)), SlotSet("order_limit", str(limit_val))]

        dispatcher.utter_message(text=f"❌ {result.get('error', 'No orders found.')}")
        return []


# --- Admin: Token Profile ---
class ActionAdminTokenMe(Action):
    """Get current admin token profile."""

    def name(self) -> Text:
        return "action_admin_token_me"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("ActionAdminTokenMe: Getting admin token profile")

        service = get_nop_service_cached()
        result = service.admin_get_token_me()

        if result["success"]:
            profile = result.get("profile") or {}
            message = "**🛡️ Admin Token Profile**\n\n"
            if isinstance(profile, dict):
                message += "| Field | Value |\n"
                message += "| :--- | :--- |\n"
                for key, value in profile.items():
                    key_lower = str(key).lower()
                    display_value = value
                    if any(s in key_lower for s in ["secret", "token", "apikey", "api_key"]):
                        display_value = "[REDACTED]"
                    message += f"| **{key}** | {display_value} |\n"
                secret_key = None
                key_candidates = [
                    "secret_key",
                    "secretKey",
                    "api_key",
                    "apiKey",
                    "token",
                    "access_token",
                    "accessToken",
                    "jwt",
                    "key",
                ]
                for candidate in key_candidates:
                    if candidate in profile and profile.get(candidate):
                        secret_key = str(profile.get(candidate)).strip()
                        break

                if secret_key:
                    set_config_value("NOP_SECRET_KEY", secret_key)
                    service.secret_key = secret_key
                    message += "\n✅ NOP secret key updated."
            else:
                message += str(profile)

            dispatcher.utter_message(
                text=message,
                buttons=[
                    {"title": "👤 Find Customer", "payload": "/admin_find_customer"},
                    {"title": "📦 Find Product", "payload": "/admin_find_product"}
                ]
            )
            return []


# --- Admin: Current Admin User ---
class ActionAdminMe(Action):
    """Get current admin user profile."""

    def name(self) -> Text:
        return "action_admin_me"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("ActionAdminMe: Getting admin user profile")

        service = get_nop_service_cached()
        result = service.admin_get_me()

        if result.get("success") and isinstance(result.get("profile"), dict):
            profile = result["profile"]
            first_name = profile.get("firstName") or profile.get("first_name")
            last_name = profile.get("lastName") or profile.get("last_name")
            name_candidates = [
                f"{first_name or ''} {last_name or ''}".strip() if first_name or last_name else None,
                profile.get("name"),
                profile.get("fullName"),
                profile.get("full_name"),
                profile.get("userName"),
                profile.get("username"),
                profile.get("email"),
            ]
            display_name = next((n for n in name_candidates if n), "Admin")

            dispatcher.utter_message(
                json_message={
                    "admin_me": True,
                    "display_name": display_name,
                    "profile": profile
                }
            )
            return []

        dispatcher.utter_message(
            json_message={
                "admin_me": False,
                "display_name": "Admin",
                "error": result.get("error")
            }
        )
        return []

        dispatcher.utter_message(text=f"❌ {result.get('error', 'Failed to retrieve admin profile.')}")
        return []

# =============================================================================
# Knowledge Base Search Action
# =============================================================================
from actions.conversation_db import search_kb, get_kb_cache_stats, refresh_kb_cache

class ActionKbSearch(Action):
    def name(self) -> Text:
        return "action_kb_search"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # Get user's last message
        last_message = tracker.latest_message.get('text')
        if not last_message:
            dispatcher.utter_message(text="I'm sorry, I didn't catch that.")
            return []

        # Search KB (In-memory cache search - fast!)
        results = search_kb(last_message)

        if results:
            # Get the best matching result (first one - highest score)
            best_match = results[0]
            title = best_match.get('title', 'Knowledge Base Article')
            content = best_match.get('content', '')
            url = best_match.get('url')

            # Clean and format the content snippet
            snippet = content.strip().replace('\n', ' ')
            snippet = snippet[:500] + "..." if len(snippet) > 500 else snippet

            # Build message with link
            link_text = f"🔗 [View Full Article]({url})" if url else ""
            message = f"📖 **{title}**\n{snippet}\n{link_text}"

            dispatcher.utter_message(text=message)
        else:
            # Fallback message with helpful buttons
            dispatcher.utter_message(
                text="I'm sorry, I couldn't find an answer to that in my knowledge base. Here's what I can help you with:",
                buttons=[
                    {"title": "🛒 Order", "payload": "/track_order"},
                    {"title": "📦 Product", "payload": "/search_products"},
                    {"title": "👤 Customer", "payload": "/admin_find_customer"}
                ]
            )

        return []


class ActionKbCacheStatus(Action):
    """Check knowledge base cache status and statistics."""

    def name(self) -> Text:
        return "action_kb_cache_status"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # Get cache stats
        stats = get_kb_cache_stats()

        status_icon = "✅" if stats['enabled'] else "❌"

        message = f"**{status_icon} Knowledge Base Cache Status**\n\n"
        message += "| Property | Value |\n"
        message += "| :--- | :--- |\n"
        message += f"| **Status** | {'Enabled' if stats['enabled'] else 'Disabled'} |\n"
        message += f"| **Articles** | {stats['articles_count']} |\n"
        message += f"| **Chunks** | {stats['chunks_count']} |\n"
        message += f"| **Cache Size** | {stats['cache_size_kb']:.2f} KB |\n"

        if stats['loaded_at']:
            message += f"| **Loaded At** | {stats['loaded_at']} |\n"

        dispatcher.utter_message(text=message)

        return []
