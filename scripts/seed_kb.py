
import sys
import os

# Add parent directory to path to import actions
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from actions.conversation_db import add_kb_article

articles = [
    {
        "title": "Managing Orders",
        "content": "To manage orders, go to **Sales > Orders**. You can view, edit, and update order statuses here. \n\n![Orders Page](https://docs.nopcommerce.com/en/running-your-store/order-management/images/orders-list.png)",
        "url": "https://docs.nopcommerce.com/en/running-your-store/order-management/orders.html"
    },
    {
        "title": "Adding Products",
        "content": "To add a product, go to **Catalog > Products** and click **Add new**. Fill in the details like name, SKU, and price.",
        "url": "https://docs.nopcommerce.com/en/running-your-store/catalog/products/add-product.html"
    },
     {
        "title": "Shipping Settings",
        "content": "Configure shipping providers under **Configuration > Shipping > Providers**. Enable the methods you want to offer.",
        "url": "https://docs.nopcommerce.com/en/running-your-store/shipping/index.html"
    }
]

def main():
    print("Seeding Knowledge Base...")
    for article in articles:
        if add_kb_article(article['title'], article['content'], article['url']):
            print(f"Added: {article['title']}")
        else:
            print(f"Failed: {article['title']}")
    print("Done.")

if __name__ == "__main__":
    main()
