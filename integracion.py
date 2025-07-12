# integracion.py (con RabbitMQ)
import odoorpc
import webdav3.client as wc
import pika # <-- LIBRERÍA NUEVA
import json # <-- LIBRERÍA NUEVA

# --- CONFIGURACIÓN ---
# Odoo
ODOO_URL = 'localhost'
ODOO_PORT = 8069
ODOO_DB = 'odoo'
ODOO_USER = 'odoo'
ODOO_PASSWORD = 'admin'

# Nextcloud
NEXTCLOUD_URL = 'http://localhost:8084'
NEXTCLOUD_USER = 'admin'
NEXTCLOUD_PASSWORD = 'admin'

# RabbitMQ
RABBITMQ_HOST = 'localhost'

def send_message_to_rabbitmq(message_body):
    """
    Establece conexión con RabbitMQ y envía un mensaje.
    """
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
        channel = connection.channel()

        # Declara una cola para notificaciones, si no existe
        channel.queue_declare(queue='new_customer_notifications')

        channel.basic_publish(
            exchange='',
            routing_key='new_customer_notifications',
            body=json.dumps(message_body) # Enviamos el mensaje como un JSON
        )
        print(f" -> Mensaje enviado a RabbitMQ: {message_body}")
        connection.close()
    except Exception as e:
        print(f" -> Error al enviar mensaje a RabbitMQ: {e}")


def sincronizar_clientes():
    """
    Busca clientes en Odoo, crea carpeta en Nextcloud y envía mensaje a RabbitMQ.
    """
    print("Iniciando sincronización...")

    # Conexión a Odoo
    try:
        odoo = odoorpc.ODOO(ODOO_URL, port=ODOO_PORT)
        odoo.login(ODOO_DB, ODOO_USER, ODOO_PASSWORD)
        print("Conexión a Odoo exitosa.")
    except Exception as e:
        print(f"Error al conectar con Odoo: {e}")
        return

    # Conexión a Nextcloud
    try:
        options = {
            'webdav_hostname': f"{NEXTCLOUD_URL}/remote.php/dav/files/{NEXTCLOUD_USER}/",
            'webdav_login':    NEXTCLOUD_USER,
            'webdav_password': NEXTCLOUD_PASSWORD
        }
        client = wc.Client(options)
        print("Conexión a Nextcloud exitosa.")
    except Exception as e:
        print(f"Error al conectar con Nextcloud: {e}")
        return

    Partner = odoo.env['res.partner']
    partner_ids = Partner.search([('is_company', '=', False), ('name', '!=', False)])

    if not client.check("Clientes"):
        client.mkdir("Clientes")

    for pid in partner_ids:
        customer_data = Partner.browse(pid)
        customer_folder_name = customer_data.name.replace(" ", "_")
        full_path = f"Clientes/{customer_folder_name}"
        print(f"\nProcesando cliente: {customer_data.name}")

        # Solo procesamos clientes que no tienen carpeta aún
        if not client.check(full_path):
            print(f" -> Creando carpeta '{full_path}' en Nextcloud...")
            client.mkdir(full_path)
            print(" -> Carpeta creada exitosamente.")
            client.upload_sync(remote_path=f"{full_path}/bienvenida.txt", local_path="bienvenida.txt")
            print(" -> Archivo de bienvenida subido a Nextcloud.")

            # --- INICIO DE LA MODIFICACIÓN ---
            # 6. Enviar notificación a RabbitMQ
            message = {
                "customer_id": customer_data.id,
                "name": customer_data.name,
                "email": customer_data.email,
                "event_type": "NEW_CUSTOMER"
            }
            send_message_to_rabbitmq(message)
            # --- FIN DE LA MODIFICACIÓN ---
        else:
            print(f" -> La carpeta '{full_path}' ya existe. Omitiendo.")

if __name__ == "__main__":
    sincronizar_clientes()  