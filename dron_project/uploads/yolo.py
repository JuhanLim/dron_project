from ultralytics import YOLO
import cv2
import numpy as np
import os 
def yolo_model_create():
    print("Yolo model_create~~~~~~~~~~")
    trained_yolo = YOLO(r"C:\Users\v\Desktop\dron_project\nano_finetunning.pt")
    return trained_yolo

trained_yolo = yolo_model_create()

def predict_yolo(img_path):
    
    print("파노라마 생성 완료 yolo 작업 시작 ----------- ")
    #img_path = r"C:\Users\v\Desktop\dron_project\test_image\A3_T1_W1_H1_S102_1_20211022_112359_0568.jpg"
    frame = cv2.imread(img_path)
    # Extract bounding boxes, masks, and classification probabilities


# Run inference on the image
    result = trained_yolo([frame])[0]
    #predict = trained_yolo.predict(img_path)
    boxes = result.boxes
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    probs = result.probs
        # # Visualize results (example: drawing bounding boxes)
    for box in boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])  # Convert to integers
        cv2.rectangle(mask, (x1, y1), (x2, y2), 255, -1)
    inpainted_image = cv2.inpaint(frame, mask, inpaintRadius=7, flags=cv2.INPAINT_NS)
    processed_img_path = os.path.join('processed', os.path.basename(img_path))
    os.makedirs('processed', exist_ok=True)
    print("처리된 이미지 저장 경로 : " ,processed_img_path)
    cv2.imwrite(processed_img_path, inpainted_image)
    return processed_img_path


# img_path = r"C:\Users\v\Desktop\dron_project\test_image\A3_T1_W1_H1_S102_1_20211022_112359_0568.jpg"


# # Extract bounding boxes, masks, and classification probabilities
# boxes = result.boxes
# mask = np.zeros(frame.shape[:2], dtype=np.uint8)
# probs = result.probs

# # Visualize results (example: drawing bounding boxes)
# for box in boxes:
#     x1, y1, x2, y2 = map(int, box.xyxy[0])  # Convert to integers
#     cv2.rectangle(mask, (x1, y1), (x2, y2), 255, -1)

# inpainted_image = cv2.inpaint(frame, mask, inpaintRadius=7, flags=cv2.INPAINT_NS) # 영역이 크거나 복잡한경우 NS(느림) , 아니면 TELEA 

# # 박스는 안치기
# # for box in boxes:
# #     x1, y1, x2, y2 = map(int, box.xyxy[0])  # Convert to integers
# #     confidence = box.conf[0]  # Confidence score
# #     class_id = box.cls[0]  # Class ID
# #     label = trained_yolo.names[int(class_id)]  # Class label

# #     # Draw bounding box and label on the inpainted image for visualization
# #     cv2.rectangle(inpainted_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
# #     cv2.putText(inpainted_image, f'{label}: {confidence:.2f}', (x1, y1 - 10),
# #                 cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

# # Display the original image and the inpainted image
# cv2.imshow('Original Image', frame)
# cv2.imshow('Inpainted Image', inpainted_image)
# cv2.waitKey(0)
# cv2.destroyAllWindows()