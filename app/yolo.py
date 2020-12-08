import cv2
import numpy as np
import im_utils


class Yolo:

    def __init__(self, net, classes, conf):
        self.net = cv2.dnn.readNet(net, conf)
        self.classes = classes
        layer_names = self.net.getLayerNames()
        self.output_layers = [layer_names[i[0] - 1] for i in self.net.getUnconnectedOutLayers()]

    def get_detected_objects(self, img_path, conf_thresh=0.6, ratio_thresh=0.05, show=False):
        if im_utils.is_url(img_path):
            real_img = im_utils.imread_url(img_path, flags=1)
        else:
            real_img = cv2.imread(img_path)
        # img = cv2.copyMakeBorder(img, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        resize_ratio = 0.4
        img = cv2.resize(real_img, None, fx=resize_ratio, fy=resize_ratio)
        height, width, channels = img.shape

        # Detecting objects
        blob = cv2.dnn.blobFromImage(img, 0.00392, (416, 416), (0, 0, 0), True, crop=False)

        self.net.setInput(blob)
        outs = self.net.forward(self.output_layers)

        # Show informations on image
        class_ids = []
        confidences = []
        boxes = []
        detected_objects = []
        for out in outs:
            for detection in out:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                if confidence > conf_thresh:
                    # Object detected
                    center_x = int(detection[0] * width)
                    center_y = int(detection[1] * height)
                    w = int(detection[2] * width)
                    h = int(detection[3] * height)

                    # Rectangle coordinates
                    x = int(center_x - w / 2)
                    y = int(center_y - h / 2)

                    boxes.append([x, y, w, h])
                    confidences.append(float(confidence))
                    class_ids.append(class_id)

        indexes = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)
        for i in range(len(boxes)):
            if i in indexes:
                x, y, w, h = boxes[i]
                ratio = w / h
                official_card_w, official_card_h = 63, 88  # mm
                # Cards have specific ratio, test confidence over this criteria
                if abs(ratio - official_card_w / official_card_h) > ratio_thresh:
                    continue
                real_x, real_y = x, y
                if x < 0:
                    real_x = 0
                if y < 0:
                    real_y = 0
                # Retrieve corresponding box on original image (not resized)
                r = 1/resize_ratio
                n_y = int(real_y * r)
                n_y2 = int(y * r)
                n_x = int(real_x * r)
                n_x2 = int(x * r)
                n_h = int(h * r)
                n_w = int(w * r)
                detected_objects.append((real_img[n_y:n_y2 + n_h, n_x:n_x2 + n_w], confidences[i]))

                if show:
                    # Drawing
                    label = str(self.classes[class_ids[i]]) + "" + str(round(confidences[i], 2))
                    color = 125
                    cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
                    cv2.putText(img, label, (x, y + 30), cv2.FONT_HERSHEY_PLAIN, 3, color, 2)
        if show:
            cv2.imshow("Image", img)
            cv2.waitKey()
            cv2.destroyAllWindows()

        return detected_objects


if __name__ == "__main__":
    pass


