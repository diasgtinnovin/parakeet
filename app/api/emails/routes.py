from flask import jsonify, Response
from app import db
from app.models.email import Email
from . import emails_bp
import logging

logger = logging.getLogger(__name__)

@emails_bp.route('/track/open/<tracking_pixel_id>', methods=['GET'])
def track_email_open(tracking_pixel_id):
    """Track email open via tracking pixel"""
    try:
        email_record = Email.query.filter_by(tracking_pixel_id=tracking_pixel_id).first()
        
        if email_record and not email_record.is_opened:
            email_record.is_opened = True
            email_record.opened_at = db.func.now()
            db.session.commit()
            
            logger.info(f"Email {email_record.id} opened")
        
        # Return 1x1 transparent pixel
        pixel_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82'
        return Response(pixel_data, mimetype='image/png')
        
    except Exception as e:
        logger.error(f"Error tracking email open: {e}")
        return jsonify({'error': 'Internal server error'}), 500

