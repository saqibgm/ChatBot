"""
nopCommerce API Service Module
Handles all API interactions with nopCommerce v4.9
"""

import logging
import requests
import base64
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class NopCommerceService:
    """
    nopCommerce REST API Service
    
    Provides methods for:
    - Customer authentication (login/logout/token management)
    - Product operations (search, details, stock)
    - Order operations (tracking, invoice, status updates)
    """
    
    def __init__(self, api_url: str, secret_key: str, admin_username: Optional[str] = None, admin_password: Optional[str] = None, verify_ssl: bool = True):
        """
        Initialize the nopCommerce service.
        
        Args:
            api_url: Base URL for the nopCommerce API (e.g., https://store.com/api)
            secret_key: The API secret key generated in nopCommerce admin
        """
        self.api_url = api_url.rstrip('/')
        self.secret_key = secret_key
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.admin_access_token = None
        self.admin_token_expiry = None
        self.admin_profile = None
        self.verify_ssl = verify_ssl

    def _get_public_base_url(self) -> str:
        """Get base URL for public API endpoints."""
        base_url = self.api_url
        if base_url.endswith("/api"):
            base_url = base_url[:-4]
        return base_url
    
    # =========================================================================
    # AUTHENTICATION
    # =========================================================================
    
    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate a customer/user with nopCommerce.
        
        Args:
            username: Customer email or username
            password: Customer password
            
        Returns:
            Dict with 'success', 'access_token', 'customer_id', 'customer_name', 'error'
        """
        # Try different authentication endpoints based on common API plugin patterns
        endpoints = [
            "/token",  # SevenSpikes/api-plugin-for-nopcommerce
            "/api-backend/Authenticate/GetToken",  # Official Web API
            "/api/PublicCustomer/Login",  # NopAdvance
        ]
        
        for endpoint in endpoints:
            result = self._try_login_endpoint(endpoint, username, password)
            if result.get("success"):
                return result
        
        # If none worked, return the last error
        return {
            "success": False,
            "access_token": None,
            "refresh_token": None,
            "customer_id": None,
            "customer_name": None,
            "error": "Authentication failed. Please check your credentials and API configuration."
        }
    
    def _try_login_endpoint(self, endpoint: str, username: str, password: str) -> Dict[str, Any]:
        """Try a specific login endpoint."""
        url = f"{self.api_url}{endpoint}"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        # Add API key header if available (for plugins that require it)
        if self.secret_key:
            headers["X-API-KEY"] = self.secret_key
            headers["Authorization"] = f"Bearer {self.secret_key}"
        
        # Standard payload format
        payload = {
            "username": username,
            "email": username,
            "UsernameOrEmail": username,
            "password": password,
            "Password": password,
            "grant_type": "password"
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15, verify=self.verify_ssl)
            
            if response.status_code == 200:
                data = response.json()
                
                # Handle different response formats from various plugins
                access_token = (
                    data.get("access_token") or 
                    data.get("AccessToken") or 
                    data.get("token") or
                    data.get("Token")
                )
                
                refresh_token = (
                    data.get("refresh_token") or 
                    data.get("RefreshToken")
                )
                
                if access_token:
                    self.access_token = access_token
                    self.refresh_token = refresh_token
                    
                    # Calculate token expiry
                    expires_in = data.get("expires_in", data.get("ExpiresIn", 3600))
                    self.token_expiry = datetime.now() + timedelta(seconds=expires_in)
                    
                    # Get customer info
                    customer_info = self._get_current_customer()
                    
                    return {
                        "success": True,
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                        "customer_id": customer_info.get("id") if customer_info else data.get("customer_id"),
                        "customer_name": customer_info.get("name") if customer_info else username,
                        "error": None
                    }
            
            # Parse error message
            error_msg = "Invalid username or password"
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    error_msg = error_data.get("message") or error_data.get("Message") or error_msg
                elif isinstance(error_data, list) and len(error_data) > 0:
                    error_msg = str(error_data[0])
            except:
                pass
            
            return {
                "success": False,
                "access_token": None,
                "refresh_token": None,
                "customer_id": None,
                "customer_name": None,
                "error": error_msg
            }
            
        except requests.exceptions.RequestException as e:
            logger.debug(f"Login attempt to {endpoint} failed: {e}")
            return {
                "success": False,
                "access_token": None,
                "refresh_token": None,
                "customer_id": None,
                "customer_name": None,
                "error": f"Connection error: {str(e)}"
            }
    
    def _get_current_customer(self) -> Optional[Dict[str, Any]]:
        """Get current logged-in customer info."""
        if not self.access_token:
            return None
        
        endpoints = [
            "/customers/current",
            "/api/customers/current",
            "/api/PublicCustomer/GetCurrentCustomer"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.api_url}{endpoint}"
                headers = self._get_auth_headers()
                response = requests.get(url, headers=headers, timeout=10, verify=self.verify_ssl)
                
                if response.status_code == 200:
                    data = response.json()
                    # Handle nested response
                    customer = data.get("customer") or data.get("Customer") or data
                    return {
                        "id": customer.get("id") or customer.get("Id"),
                        "name": customer.get("first_name") or customer.get("FirstName") or customer.get("email"),
                        "email": customer.get("email") or customer.get("Email"),
                        "full_name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
                    }
            except:
                continue
        
        return None
    
    def refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token."""
        if not self.refresh_token:
            return False
        
        url = f"{self.api_url}/token"
        headers = {"Content-Type": "application/json"}
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10, verify=self.verify_ssl)
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token", self.refresh_token)
                expires_in = data.get("expires_in", 3600)
                self.token_expiry = datetime.now() + timedelta(seconds=expires_in)
                return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Token refresh failed: {e}")
        
        return False
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get headers with authentication token."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        if self.secret_key:
            headers["X-API-KEY"] = self.secret_key
        
        return headers

    def _get_admin_base_url(self) -> str:
        """Get base URL for admin API endpoints."""
        base_url = self.api_url
        if base_url.endswith("/api"):
            base_url = base_url[:-4]
        return base_url

    def _get_admin_headers(self) -> Dict[str, str]:
        """Get headers with admin authentication token."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.admin_access_token:
            headers["Authorization"] = f"Bearer {self.admin_access_token}"
        if self.secret_key:
            headers["X-API-KEY"] = self.secret_key
        return headers

    def _is_admin_token_valid(self) -> bool:
        """Check if the current admin token is still valid."""
        if not self.admin_access_token:
            return False
        if not self.admin_token_expiry:
            return True
        return datetime.now() < self.admin_token_expiry

    def admin_login(self, username: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
        """Authenticate as admin using the Admin API token endpoint."""
        username = username or self.admin_username
        password = password or self.admin_password
        if not username or not password:
            return {
                "success": False,
                "access_token": None,
                "error": "Admin credentials are not configured."
            }

        url = f"{self._get_admin_base_url()}/api/admin/token"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.secret_key:
            headers["X-API-KEY"] = self.secret_key

        payload = {
            "username": username,
            "password": password
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15, verify=self.verify_ssl)
            if response.status_code == 200:
                data = response.json()
                token = (
                    data.get("AccessToken") or
                    data.get("accessToken") or
                    data.get("access_token") or
                    data.get("token") or
                    data.get("Token") or
                    data.get("jwt")
                )
                if token:
                    self.admin_access_token = token
                    # Store admin user profile from token response
                    self.admin_profile = {
                        "username": username,
                        "email": data.get("email") or data.get("Email") or username,
                        "firstName": data.get("firstName") or data.get("FirstName") or data.get("first_name"),
                        "lastName": data.get("lastName") or data.get("LastName") or data.get("last_name"),
                        "name": data.get("name") or data.get("Name") or data.get("displayName") or data.get("DisplayName"),
                    }
                    expires_in = data.get("expires_in") or data.get("expiresIn")
                    if expires_in:
                        try:
                            self.admin_token_expiry = datetime.now() + timedelta(seconds=int(expires_in))
                        except (ValueError, TypeError):
                            self.admin_token_expiry = None
                    return {
                        "success": True,
                        "access_token": token,
                        "error": None
                    }

            error_msg = "Admin authentication failed."
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    error_msg = error_data.get("message") or error_data.get("Message") or error_msg
            except Exception:
                pass

            return {
                "success": False,
                "access_token": None,
                "error": error_msg
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Admin login failed: {e}")
            return {
                "success": False,
                "access_token": None,
                "error": f"Connection error: {str(e)}"
            }

    def _ensure_admin_token(self) -> bool:
        """Ensure an admin token is available."""
        if self._is_admin_token_valid():
            # Validate token via /api/admin/token/me
            token_check = self.admin_get_token_me()
            if token_check.get("success"):
                return True
        result = self.admin_login()
        return result.get("success", False)

    def _admin_request(self, method: str, path: str, **kwargs) -> Optional[requests.Response]:
        """Perform an admin API request with automatic token handling."""
        if not self._ensure_admin_token():
            return None

        url = f"{self._get_admin_base_url()}{path}"
        headers = kwargs.pop("headers", None) or self._get_admin_headers()
        try:
            response = requests.request(method, url, headers=headers, timeout=15, verify=self.verify_ssl, **kwargs)
            if response.status_code in [401, 403] and self.admin_username and self.admin_password:
                if self.admin_login().get("success"):
                    headers = self._get_admin_headers()
                    response = requests.request(method, url, headers=headers, timeout=15, verify=self.verify_ssl, **kwargs)
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Admin request failed for {path}: {e}")
            return None
    
    def is_token_valid(self) -> bool:
        """Check if the current access token is still valid."""
        if not self.access_token or not self.token_expiry:
            return False
        return datetime.now() < self.token_expiry

    def _normalize_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize product data from different API formats."""
        return {
            "id": product.get("id") or product.get("Id"),
            "name": product.get("name") or product.get("Name"),
            "short_description": product.get("short_description") or product.get("ShortDescription") or "",
            "full_description": product.get("full_description") or product.get("FullDescription") or "",
            "sku": product.get("sku") or product.get("Sku") or "",
            "price": product.get("price") or product.get("Price") or 0,
            "old_price": product.get("old_price") or product.get("OldPrice"),
            "stock_quantity": product.get("stock_quantity") or product.get("StockQuantity") or 0,
            "in_stock": (product.get("stock_quantity") or product.get("StockQuantity") or 0) > 0,
            "manage_inventory": product.get("manage_inventory_method") or product.get("ManageInventoryMethod"),
            "image_url": self._get_product_image(product),
            "categories": product.get("categories") or product.get("Categories") or []
        }

    def _normalize_customer(self, customer: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize customer data."""
        return {
            "id": customer.get("id") or customer.get("Id"),
            "email": customer.get("email") or customer.get("Email"),
            "username": customer.get("username") or customer.get("Username") or customer.get("email"),
            "first_name": customer.get("first_name") or customer.get("FirstName"),
            "last_name": customer.get("last_name") or customer.get("LastName"),
            "full_name": customer.get("full_name") or customer.get("FullName") or f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
            "phone": customer.get("phone") or customer.get("Phone"),
            "is_active": customer.get("is_active") or customer.get("IsActive"),
        }

    def _normalize_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize order data."""
        return {
            "id": order.get("id") or order.get("Id"),
            "order_number": order.get("custom_order_number") or order.get("order_number") or order.get("id") or order.get("Id"),
            "status": order.get("order_status") or order.get("OrderStatus") or order.get("status") or order.get("Status") or "Unknown",
            "payment_status": order.get("payment_status") or order.get("PaymentStatus"),
            "shipping_status": order.get("shipping_status") or order.get("ShippingStatus"),
            "total": order.get("order_total") or order.get("OrderTotal") or order.get("total") or 0,
            "created_on": order.get("created_on") or order.get("CreatedOn") or order.get("created_on_utc") or order.get("CreatedOnUtc"),
            "items": order.get("order_items") or order.get("OrderItems") or order.get("items") or []
        }

    # =========================================================================
    # ADMIN API
    # =========================================================================

    def admin_get_product(self, product_id: int) -> Dict[str, Any]:
        """Get product details from Admin API."""
        response = self._admin_request("GET", f"/api/admin/products/{product_id}")
        if response and response.status_code == 200:
            data = response.json()
            product = data.get("product") or data.get("Product") or data
            return {
                "success": True,
                "product": self._normalize_product(product),
                "error": None
            }
        return {
            "success": False,
            "product": None,
            "error": f"Product with ID {product_id} not found."
        }

    def admin_get_product_stock(self, product_id: int) -> Dict[str, Any]:
        """Get product stock from Admin API."""
        response = self._admin_request("GET", f"/api/admin/products/{product_id}/stock")
        if response and response.status_code == 200:
            data = response.json()
            stock_quantity = data.get("stockQuantity") or data.get("stock_quantity") or data.get("StockQuantity") or 0
            product_info = self.admin_get_product(product_id)
            product_name = None
            sku = None
            if product_info.get("success"):
                product = product_info.get("product") or {}
                product_name = product.get("name")
                sku = product.get("sku")
            return {
                "success": True,
                "product_id": product_id,
                "product_name": product_name,
                "stock_quantity": stock_quantity,
                "in_stock": int(stock_quantity) > 0,
                "sku": sku,
                "error": None
            }
        return {
            "success": False,
            "product_id": product_id,
            "product_name": None,
            "stock_quantity": 0,
            "in_stock": False,
            "sku": None,
            "error": f"Failed to get stock for product {product_id}."
        }

    def admin_update_product_stock(self, product_id: int, quantity: int) -> Dict[str, Any]:
        """Update product stock via Admin API."""
        payload = {"stockQuantity": quantity}
        response = self._admin_request("POST", f"/api/admin/products/{product_id}/stock", json=payload)
        if response and response.status_code == 200:
            return {
                "success": True,
                "product_id": product_id,
                "new_quantity": quantity,
                "error": None
            }
        return {
            "success": False,
            "product_id": product_id,
            "new_quantity": None,
            "error": f"Failed to update stock for product {product_id}."
        }

    def admin_get_order(self, order_id: int) -> Dict[str, Any]:
        """Get order details from Admin API."""
        response = self._admin_request("GET", f"/api/admin/orders/{order_id}")
        if response and response.status_code == 200:
            data = response.json()
            order = data.get("order") or data.get("Order") or data
            return {
                "success": True,
                "order": self._normalize_order(order),
                "error": None
            }
        return {
            "success": False,
            "order": None,
            "error": f"Order with ID {order_id} not found."
        }

    def admin_update_order_status(self, order_id: int, new_status: str) -> Dict[str, Any]:
        """Update order status via Admin API."""
        status_map = {
            "pending": 10,
            "processing": 20,
            "complete": 30,
            "completed": 30,
            "cancelled": 40,
            "canceled": 40,
        }
        status_id = None
        if isinstance(new_status, int):
            status_id = new_status
        else:
            text_status = str(new_status).strip()
            if text_status.isdigit():
                status_id = int(text_status)
            else:
                status_id = status_map.get(text_status.lower())

        if status_id is None:
            return {
                "success": False,
                "order_id": order_id,
                "new_status": None,
                "error": "Order status must be a valid status ID (e.g., 10, 20, 30, 40)."
            }

        payload = {"orderStatusId": status_id}
        response = self._admin_request("POST", f"/api/admin/orders/{order_id}/status", json=payload)
        if response and response.status_code == 200:
            return {
                "success": True,
                "order_id": order_id,
                "new_status": status_id,
                "error": None
            }
        return {
            "success": False,
            "order_id": order_id,
            "new_status": None,
            "error": f"Failed to update status for order {order_id}."
        }

    def admin_get_order_invoice_pdf(self, order_id: int) -> Dict[str, Any]:
        """Get order invoice from Admin API."""
        response = self._admin_request("GET", f"/api/admin/orders/{order_id}/invoice", headers={"Accept": "application/pdf"})
        if response and response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            if "pdf" in content_type.lower() or response.content[:4] == b"%PDF":
                pdf_base64 = base64.b64encode(response.content).decode("utf-8")
                return {
                    "success": True,
                    "pdf_data": pdf_base64,
                    "filename": f"invoice_order_{order_id}.pdf",
                    "error": None
                }
            try:
                data = response.json()
                pdf_data = data.get("pdf") or data.get("pdf_data")
                if pdf_data:
                    return {
                        "success": True,
                        "pdf_data": pdf_data,
                        "filename": data.get("filename") or f"invoice_order_{order_id}.pdf",
                        "error": None
                    }
            except Exception:
                pass
        return {
            "success": False,
            "pdf_data": None,
            "filename": None,
            "error": f"Failed to retrieve invoice for order {order_id}."
        }

    def admin_get_customer(self, customer_id: int) -> Dict[str, Any]:
        """Get customer by ID from Admin API."""
        response = self._admin_request("GET", f"/api/admin/customers/{customer_id}")
        if response and response.status_code == 200:
            data = response.json()
            customer = data.get("customer") or data.get("Customer") or data
            return {
                "success": True,
                "customer": self._normalize_customer(customer),
                "error": None
            }
        return {
            "success": False,
            "customer": None,
            "error": f"Customer with ID {customer_id} not found."
        }

    def admin_get_customer_details(self, customer_id: int) -> Dict[str, Any]:
        """Get customer details from Admin API."""
        response = self._admin_request("GET", f"/api/admin/customers/{customer_id}/details")
        if response and response.status_code == 200:
            data = response.json()
            customer = data.get("customer") or data.get("Customer") or data
            return {
                "success": True,
                "customer": self._normalize_customer(customer),
                "details": data,
                "error": None
            }
        return {
            "success": False,
            "customer": None,
            "details": None,
            "error": f"Customer details not found for ID {customer_id}."
        }

    def admin_find_product(self, identifier: str) -> Dict[str, Any]:
        """Find product by identifier (SKU or name) via Admin API."""
        response = self._admin_request("GET", f"/api/admin/products/find/{identifier}")
        if response and response.status_code == 200:
            data = response.json()
            product = data.get("product") or data.get("Product") or data
            return {
                "success": True,
                "product": self._normalize_product(product),
                "error": None
            }
        return {
            "success": False,
            "product": None,
            "error": f"Product not found for identifier '{identifier}'."
        }

    def admin_find_customer(self, query: str) -> Dict[str, Any]:
        """Find customers by query string via Admin API."""
        response = self._admin_request("GET", f"/api/admin/customers/find/{query}")
        if response and response.status_code == 200:
            data = response.json()
            customers = data.get("customers") or data.get("Customers") or data
            if isinstance(customers, dict):
                customers = customers.get("items") or customers.get("Items") or [customers]
            if not isinstance(customers, list):
                customers = [customers] if customers else []
            return {
                "success": True,
                "customers": [self._normalize_customer(c) for c in customers],
                "error": None
            }
        return {
            "success": False,
            "customers": [],
            "error": f"No customers found for '{query}'."
        }

    def admin_get_customer_last_orders(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Get last N orders for a customer (by id or query) via Admin API."""
        response = self._admin_request("GET", f"/api/admin/customers/{query}/orders/last/{limit}")
        if response and response.status_code == 200:
            data = response.json()
            orders = data.get("orders") or data.get("Orders") or data
            if isinstance(orders, dict):
                orders = orders.get("items") or orders.get("Items") or [orders]
            if not isinstance(orders, list):
                orders = [orders] if orders else []
            return {
                "success": True,
                "orders": [self._normalize_order(o) for o in orders],
                "error": None
            }
        return {
            "success": False,
            "orders": [],
            "error": f"No recent orders found for '{query}'."
        }

    def admin_get_token_me(self) -> Dict[str, Any]:
        """Get current admin token profile info via Admin API."""
        if not self.access_token:
            return {
                "success": False,
                "profile": None,
                "error": "No admin token available."
            }

        url = f"{self._get_admin_base_url()}/api/admin/token/me"
        headers = self._get_admin_headers()
        try:
            response = requests.get(url, headers=headers, timeout=15, verify=self.verify_ssl)
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "profile": data,
                    "error": None
                }
            return {
                "success": False,
                "profile": None,
                "error": f"Failed to retrieve admin token profile (status {response.status_code})."
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Admin token/me request failed: {e}")
            return {
                "success": False,
                "profile": None,
                "error": f"Connection error: {str(e)}"
            }

    def admin_get_me(self) -> Dict[str, Any]:
        """Get current admin user info via Admin API."""
        # Ensure we have a valid admin token first
        if not self._ensure_admin_token():
            return {
                "success": False,
                "profile": None,
                "error": "Could not authenticate with admin API."
            }
        
        # Use stored profile from login response if available
        if hasattr(self, 'admin_profile') and self.admin_profile:
            return {
                "success": True,
                "profile": self.admin_profile,
                "error": None
            }

        # Fallback: try the /api/admin/me endpoint
        url = f"{self._get_admin_base_url()}/api/admin/me"
        headers = self._get_admin_headers()
        try:
            response = requests.get(url, headers=headers, timeout=15, verify=self.verify_ssl)
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "profile": data,
                    "error": None
                }
            return {
                "success": False,
                "profile": None,
                "error": f"Failed to retrieve admin profile (status {response.status_code})."
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Admin /me request failed: {e}")
            return {
                "success": False,
                "profile": None,
                "error": f"Connection error: {str(e)}"
            }
    
    # =========================================================================
    # PRODUCTS
    # =========================================================================
    
    def search_products(
        self, 
        query: str = None, 
        category_id: int = None, 
        page: int = 1,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for products.
        
        Args:
            query: Search keyword
            category_id: Filter by category ID
            page: Page number for pagination
            limit: Number of results per page
            
        Returns:
            Dict with 'success', 'products', 'total_count', 'error'
        """
        # Build query parameters
        params = {
            "page": page,
            "limit": limit,
            "fields": "id,name,short_description,price,stock_quantity,images"
        }
        
        if query:
            params["filter"] = f"name:like:{query}"
            params["q"] = query
            params["keyword"] = query
        
        if category_id:
            params["category_id"] = category_id
        
        # Try different endpoints
        endpoints = [
            "/products",
            "/api/products",
            "/api/PublicCatalog/Search"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.api_url}{endpoint}"
                headers = self._get_auth_headers()
                response = requests.get(url, headers=headers, params=params, timeout=15, verify=self.verify_ssl)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Handle different response formats
                    products = data.get("products") or data.get("Products") or data
                    if isinstance(products, dict):
                        products = products.get("items") or products.get("Items") or [products]
                    
                    if not isinstance(products, list):
                        products = [products] if products else []
                    
                    # Normalize product data
                    normalized_products = []
                    for p in products[:limit]:
                        normalized_products.append({
                            "id": p.get("id") or p.get("Id"),
                            "name": p.get("name") or p.get("Name"),
                            "short_description": p.get("short_description") or p.get("ShortDescription") or "",
                            "price": p.get("price") or p.get("Price") or 0,
                            "stock_quantity": p.get("stock_quantity") or p.get("StockQuantity") or 0,
                            "in_stock": (p.get("stock_quantity") or p.get("StockQuantity") or 0) > 0,
                            "image_url": self._get_product_image(p)
                        })
                    
                    return {
                        "success": True,
                        "products": normalized_products,
                        "total_count": data.get("total_count") or len(normalized_products),
                        "error": None
                    }
                    
            except requests.exceptions.RequestException as e:
                logger.debug(f"Product search at {endpoint} failed: {e}")
                continue
        
        return {
            "success": False,
            "products": [],
            "total_count": 0,
            "error": "Failed to search products. Please try again."
        }
    
    def _get_product_image(self, product: Dict) -> Optional[str]:
        """Extract product image URL from various response formats."""
        images = product.get("images") or product.get("Images") or []
        if images and len(images) > 0:
            img = images[0]
            return img.get("src") or img.get("Src") or img.get("url") or img.get("Url")
        
        # Try direct image fields
        return (
            product.get("image_url") or 
            product.get("ImageUrl") or 
            product.get("default_picture_url")
        )
    
    def get_product_details(self, product_id: int) -> Dict[str, Any]:
        """
        Get detailed information about a product.
        
        Args:
            product_id: The product ID
            
        Returns:
            Dict with 'success', 'product', 'error'
        """
        admin_result = self.admin_get_product(product_id)
        if admin_result.get("success"):
            return admin_result
        endpoints = [
            f"/products/{product_id}",
            f"/api/products/{product_id}",
            f"/api/PublicCatalog/Product/{product_id}"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self._get_public_base_url()}{endpoint}"
                headers = self._get_auth_headers()
                response = requests.get(url, headers=headers, timeout=10, verify=self.verify_ssl)
                
                if response.status_code == 200:
                    data = response.json()
                    product = data.get("product") or data.get("Product") or data
                    
                    return {
                        "success": True,
                        "product": self._normalize_product(product),
                        "error": None
                    }
                    
            except requests.exceptions.RequestException as e:
                logger.debug(f"Get product at {endpoint} failed: {e}")
                continue
        
        return {
            "success": False,
            "product": None,
            "error": f"Product with ID {product_id} not found."
        }
    
    def get_product_stock(self, product_id: int) -> Dict[str, Any]:
        """
        Get stock information for a product.
        
        Args:
            product_id: The product ID
            
        Returns:
            Dict with 'success', 'stock_quantity', 'in_stock', 'error'
        """
        admin_result = self.admin_get_product_stock(product_id)
        if admin_result.get("success"):
            return admin_result
        result = self.get_product_details(product_id)
        
        if result["success"]:
            product = result["product"]
            return {
                "success": True,
                "product_id": product_id,
                "product_name": product.get("name"),
                "stock_quantity": product.get("stock_quantity", 0),
                "in_stock": product.get("in_stock", False),
                "sku": product.get("sku"),
                "error": None
            }
        
        return {
            "success": False,
            "product_id": product_id,
            "product_name": None,
            "stock_quantity": 0,
            "in_stock": False,
            "sku": None,
            "error": result.get("error", "Failed to get stock information.")
        }
    
    def update_product_stock(self, product_id: int, quantity: int) -> Dict[str, Any]:
        """
        Update stock quantity for a product.
        
        Args:
            product_id: The product ID
            quantity: New stock quantity
            
        Returns:
            Dict with 'success', 'new_quantity', 'error'
        """
        admin_result = self.admin_update_product_stock(product_id, quantity)
        if admin_result.get("success"):
            return admin_result
        endpoints = [
            f"/products/{product_id}",
            f"/api/products/{product_id}",
        ]
        
        payload = {
            "product": {
                "id": product_id,
                "stock_quantity": quantity,
                "StockQuantity": quantity
            }
        }
        
        for endpoint in endpoints:
            try:
                url = f"{self.api_url}{endpoint}"
                headers = self._get_auth_headers()
                response = requests.put(url, headers=headers, json=payload, timeout=10)
                
                if response.status_code in [200, 204]:
                    logger.info(f"Updated stock for product {product_id} to {quantity}")
                    return {
                        "success": True,
                        "product_id": product_id,
                        "new_quantity": quantity,
                        "error": None
                    }
                    
            except requests.exceptions.RequestException as e:
                logger.debug(f"Update stock at {endpoint} failed: {e}")
                continue
        
        return {
            "success": False,
            "product_id": product_id,
            "new_quantity": None,
            "error": "Failed to update stock. You may not have permission for this action."
        }
    
    # =========================================================================
    # ORDERS
    # =========================================================================
    
    def get_customer_orders(
        self, 
        customer_id: int = None, 
        status: str = None,
        page: int = 1,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get orders for a customer.
        
        Args:
            customer_id: The customer ID (if None, uses current logged-in customer)
            status: Filter by order status
            page: Page number
            limit: Number of results per page
            
        Returns:
            Dict with 'success', 'orders', 'total_count', 'error'
        """
        params = {
            "page": page,
            "limit": limit
        }
        
        if customer_id:
            params["customer_id"] = customer_id
        
        if status:
            params["status"] = status
        
        endpoints = [
            "/orders",
            "/api/orders",
            "/api/PublicOrder/CustomerOrders"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.api_url}{endpoint}"
                headers = self._get_auth_headers()
                response = requests.get(url, headers=headers, params=params, timeout=15, verify=self.verify_ssl)
                
                if response.status_code == 200:
                    data = response.json()
                    orders = data.get("orders") or data.get("Orders") or data
                    
                    if isinstance(orders, dict):
                        orders = orders.get("items") or [orders]
                    
                    if not isinstance(orders, list):
                        orders = [orders] if orders else []
                    
                    # Normalize order data
                    normalized_orders = []
                    for o in orders[:limit]:
                        normalized_orders.append({
                            "id": o.get("id") or o.get("Id"),
                            "order_number": o.get("custom_order_number") or o.get("CustomOrderNumber") or o.get("id"),
                            "status": o.get("order_status") or o.get("OrderStatus") or "Unknown",
                            "total": o.get("order_total") or o.get("OrderTotal") or 0,
                            "created_on": o.get("created_on_utc") or o.get("CreatedOnUtc"),
                            "payment_status": o.get("payment_status") or o.get("PaymentStatus"),
                            "shipping_status": o.get("shipping_status") or o.get("ShippingStatus"),
                        })
                    
                    return {
                        "success": True,
                        "orders": normalized_orders,
                        "total_count": data.get("total_count") or len(normalized_orders),
                        "error": None
                    }
                    
            except requests.exceptions.RequestException as e:
                logger.debug(f"Get orders at {endpoint} failed: {e}")
                continue
        
        return {
            "success": False,
            "orders": [],
            "total_count": 0,
            "error": "Failed to retrieve orders."
        }
    
    def get_order_details(self, order_id: int) -> Dict[str, Any]:
        """
        Get detailed information about an order.
        
        Args:
            order_id: The order ID
            
        Returns:
            Dict with 'success', 'order', 'error'
        """
        admin_result = self.admin_get_order(order_id)
        if admin_result.get("success"):
            order = admin_result.get("order") or {}
            return {
                "success": True,
                "order": {
                    "id": order.get("id"),
                    "order_number": order.get("order_number"),
                    "status": order.get("status"),
                    "payment_status": order.get("payment_status"),
                    "shipping_status": order.get("shipping_status"),
                    "total": order.get("total"),
                    "subtotal": order.get("subtotal"),
                    "shipping_cost": order.get("shipping_cost"),
                    "tax": order.get("tax"),
                    "created_on": order.get("created_on"),
                    "items": order.get("items") or [],
                    "shipping_address": order.get("shipping_address"),
                    "billing_address": order.get("billing_address"),
                },
                "error": None
            }
        endpoints = [
            f"/orders/{order_id}",
            f"/api/orders/{order_id}",
            f"/api/PublicOrder/OrderDetails/{order_id}"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.api_url}{endpoint}"
                headers = self._get_auth_headers()
                response = requests.get(url, headers=headers, timeout=10, verify=self.verify_ssl)
                
                if response.status_code == 200:
                    data = response.json()
                    order = data.get("order") or data.get("Order") or data
                    
                    # Get order items
                    items = order.get("order_items") or order.get("OrderItems") or []
                    normalized_items = []
                    for item in items:
                        normalized_items.append({
                            "product_id": item.get("product_id") or item.get("ProductId"),
                            "product_name": item.get("product_name") or item.get("ProductName") or "Unknown Product",
                            "quantity": item.get("quantity") or item.get("Quantity") or 1,
                            "unit_price": item.get("unit_price_incl_tax") or item.get("UnitPriceInclTax") or 0,
                            "total": item.get("price_incl_tax") or item.get("PriceInclTax") or 0,
                        })
                    
                    return {
                        "success": True,
                        "order": {
                            "id": order.get("id") or order.get("Id"),
                            "order_number": order.get("custom_order_number") or order.get("id"),
                            "status": order.get("order_status") or order.get("OrderStatus") or "Unknown",
                            "payment_status": order.get("payment_status") or order.get("PaymentStatus"),
                            "shipping_status": order.get("shipping_status") or order.get("ShippingStatus"),
                            "total": order.get("order_total") or order.get("OrderTotal") or 0,
                            "subtotal": order.get("order_subtotal_incl_tax") or order.get("OrderSubtotalInclTax") or 0,
                            "shipping_cost": order.get("order_shipping_incl_tax") or order.get("OrderShippingInclTax") or 0,
                            "tax": order.get("order_tax") or order.get("OrderTax") or 0,
                            "created_on": order.get("created_on_utc") or order.get("CreatedOnUtc"),
                            "items": normalized_items,
                            "shipping_address": order.get("shipping_address") or order.get("ShippingAddress"),
                            "billing_address": order.get("billing_address") or order.get("BillingAddress"),
                        },
                        "error": None
                    }
                    
            except requests.exceptions.RequestException as e:
                logger.debug(f"Get order at {endpoint} failed: {e}")
                continue
        
        return {
            "success": False,
            "order": None,
            "error": f"Order with ID {order_id} not found."
        }
    
    def track_order(self, order_id: int) -> Dict[str, Any]:
        """
        Get tracking information for an order.
        
        Args:
            order_id: The order ID
            
        Returns:
            Dict with 'success', 'tracking', 'error'
        """
        result = self.get_order_details(order_id)
        
        if result["success"]:
            order = result["order"]
            
            # Determine tracking status message
            status = order.get("status", "Unknown")
            shipping_status = order.get("shipping_status", "Unknown")
            payment_status = order.get("payment_status", "Unknown")
            
            status_messages = {
                "Pending": "Your order is being processed.",
                "Processing": "Your order is being prepared for shipment.",
                "Complete": "Your order has been delivered.",
                "Cancelled": "This order has been cancelled.",
                "NotYetShipped": "Your order is waiting to be shipped.",
                "Shipped": "Your order is on its way!",
                "Delivered": "Your order has been delivered.",
                "PartiallyShipped": "Part of your order has been shipped."
            }
            
            tracking_message = status_messages.get(
                shipping_status, 
                status_messages.get(status, "Order status is being updated.")
            )
            
            return {
                "success": True,
                "tracking": {
                    "order_id": order_id,
                    "order_number": order.get("order_number"),
                    "status": status,
                    "shipping_status": shipping_status,
                    "payment_status": payment_status,
                    "message": tracking_message,
                    "total": order.get("total"),
                    "created_on": order.get("created_on"),
                    "items_count": len(order.get("items", []))
                },
                "error": None
            }
        
        return {
            "success": False,
            "tracking": None,
            "error": result.get("error", "Failed to track order.")
        }
    
    def get_order_invoice_pdf(self, order_id: int) -> Dict[str, Any]:
        """
        Get PDF invoice for an order.
        
        Args:
            order_id: The order ID
            
        Returns:
            Dict with 'success', 'pdf_data' (base64), 'filename', 'error'
        """
        admin_result = self.admin_get_order_invoice_pdf(order_id)
        if admin_result.get("success"):
            return admin_result
        endpoints = [
            f"/orders/{order_id}/pdf",
            f"/api/orders/{order_id}/pdf",
            f"/api/PublicOrder/GetPdfInvoice/{order_id}"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.api_url}{endpoint}"
                headers = self._get_auth_headers()
                headers["Accept"] = "application/pdf"
                response = requests.get(url, headers=headers, timeout=30, verify=self.verify_ssl)
                
                if response.status_code == 200:
                    # Check if response is PDF
                    content_type = response.headers.get("Content-Type", "")
                    
                    if "pdf" in content_type.lower() or response.content[:4] == b'%PDF':
                        pdf_base64 = base64.b64encode(response.content).decode('utf-8')
                        return {
                            "success": True,
                            "pdf_data": pdf_base64,
                            "filename": f"invoice_order_{order_id}.pdf",
                            "error": None
                        }
                    
            except requests.exceptions.RequestException as e:
                logger.debug(f"Get invoice at {endpoint} failed: {e}")
                continue
        
        return {
            "success": False,
            "pdf_data": None,
            "filename": None,
            "error": f"Failed to generate invoice for order {order_id}."
        }
    
    def update_order_status(self, order_id: int, new_status: str) -> Dict[str, Any]:
        """
        Update the status of an order.
        
        Args:
            order_id: The order ID
            new_status: New order status (e.g., 'Processing', 'Complete', 'Cancelled')
            
        Returns:
            Dict with 'success', 'new_status', 'error'
        """
        admin_result = self.admin_update_order_status(order_id, new_status)
        if admin_result.get("success"):
            return admin_result
        # Map status names to nopCommerce status values
        status_map = {
            "pending": "Pending",
            "processing": "Processing",
            "complete": "Complete",
            "completed": "Complete",
            "cancelled": "Cancelled",
            "canceled": "Cancelled",
        }
        
        normalized_status = status_map.get(new_status.lower(), new_status)
        
        endpoints = [
            f"/orders/{order_id}",
            f"/api/orders/{order_id}",
        ]
        
        payload = {
            "order": {
                "id": order_id,
                "order_status": normalized_status,
                "OrderStatus": normalized_status
            }
        }
        
        for endpoint in endpoints:
            try:
                url = f"{self.api_url}{endpoint}"
                headers = self._get_auth_headers()
                response = requests.put(url, headers=headers, json=payload, timeout=10)
                
                if response.status_code in [200, 204]:
                    logger.info(f"Updated order {order_id} status to {normalized_status}")
                    return {
                        "success": True,
                        "order_id": order_id,
                        "new_status": normalized_status,
                        "error": None
                    }
                    
            except requests.exceptions.RequestException as e:
                logger.debug(f"Update order status at {endpoint} failed: {e}")
                continue
        
        return {
            "success": False,
            "order_id": order_id,
            "new_status": None,
            "error": "Failed to update order status. You may not have permission for this action."
        }
    
    # =========================================================================
    # CATEGORIES (Helper)
    # =========================================================================
    
    def get_categories(self, parent_id: int = None) -> Dict[str, Any]:
        """
        Get product categories.
        
        Args:
            parent_id: Filter by parent category ID
            
        Returns:
            Dict with 'success', 'categories', 'error'
        """
        params = {}
        if parent_id:
            params["parent_category_id"] = parent_id
        
        endpoints = [
            "/categories",
            "/api/categories",
            "/api/PublicCatalog/Categories"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.api_url}{endpoint}"
                headers = self._get_auth_headers()
                response = requests.get(url, headers=headers, params=params, timeout=10, verify=self.verify_ssl)
                
                if response.status_code == 200:
                    data = response.json()
                    categories = data.get("categories") or data.get("Categories") or data
                    
                    if not isinstance(categories, list):
                        categories = [categories] if categories else []
                    
                    normalized_cats = []
                    for c in categories:
                        normalized_cats.append({
                            "id": c.get("id") or c.get("Id"),
                            "name": c.get("name") or c.get("Name"),
                            "parent_id": c.get("parent_category_id") or c.get("ParentCategoryId"),
                        })
                    
                    return {
                        "success": True,
                        "categories": normalized_cats,
                        "error": None
                    }
                    
            except requests.exceptions.RequestException as e:
                logger.debug(f"Get categories at {endpoint} failed: {e}")
                continue
        
        return {
            "success": False,
            "categories": [],
            "error": "Failed to retrieve categories."
        }
