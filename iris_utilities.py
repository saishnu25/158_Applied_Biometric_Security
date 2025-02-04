# Imports
import cv2
import os
import tensorflow
import math
import pywt
import keras
import matplotlib.pyplot as plot
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import glob
import pickle
import shutil
from scipy.interpolate import interp1d
from sklearn.model_selection import train_test_split
import typing
base_directory = 'Dataset/VISA_Iris/VISA_Iris'


def parse_iris_dataset(keep_reflections: bool = False) -> tuple[list, list, list[str]]:
    left_images: list = []
    left_labels: list[str] = []
    right_images: list = []
    right_labels: list[str] = []

    for path in glob.iglob(base_directory + '/*'):
        folder_name = os.path.basename(path)

        label = folder_name

        # Process Left Eye
        for image_path in glob.iglob(path + '/L/*'):
            image = cv2.imread(image_path)

            image_hough_processed = process_hough(image_path, image, 50)
            
            if not keep_reflections:
                image_hough_processed = remove_reflection(
                    image_hough_processed)

            if image_hough_processed is not None:
                (testimage, success) = image_hough_processed
                if success:
                    left_images.append(testimage)
                    left_labels.append(label)
            else:
                print(f"Error processing image: {image_path}")

        # Process Right Eye
        for image_path in glob.iglob(path + '/R/*'):
            image = cv2.imread(image_path)

            image_hough_processed = process_hough(image_path, image, 50)

            if not keep_reflections:
                image_hough_processed = remove_reflection(
                    image_hough_processed)

            if image_hough_processed is not None:
                (testimage, success) = image_hough_processed
                if success:
                    right_images.append(testimage)
                    right_labels.append(label)
            else:
                print(f"Error processing image: {image_path}")

    return left_images, left_labels, right_images, right_labels


def process_hough(imagepath, image, radius) -> tuple[np.ndarray, int, bool]:

    print("Processing image:", imagepath)

    # Resize the image to a fixed size
    print("Original image size:", image.shape)
    image = cv2.resize(image, (640, 480), interpolation=cv2.INTER_LINEAR)
    print("Resized image size:", image.shape)

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply median blur to reduce noise
    gray = cv2.medianBlur(gray, 11)

    # Detect edges using Canny edge detector
    edge = cv2.Canny(gray, 100, 200)

    # Apply Otsu's thresholding to get a binary image
    ret, _ = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Find circles in the binary image using Hough Circle Transform
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, 50,
                               param1=ret, param2=30, minRadius=20, maxRadius=100)

    # If circles are found
    if circles is not None:
        circles = circles[0, :, :]
        circles = np.uint16(np.around(circles))
        success = True

        # for circle in circles[0, :]:
        #     # Extract region of interest around each detected circle
        #     x, y, r = circle
        #     x = int(x)
        #     y = int(y)
        #     r = int(r)
        #     roi = image[y - r - radius: y + r +
        #                 radius, x - r - radius: x + r + radius]
        #     radius = r
        for i in circles[:]:
            roi = image[
                i[1] - i[2] - radius: i[1] + i[2] + radius,
                i[0] - i[2] - radius: i[0] + i[2] + radius
                # i[1] - i[2] : i[1] + i[2], i[0] - i[2] : i[0] + i[2]
            ]
            radius = i[2]

        return roi, success

    else:
        # If no circles are found, set the whole image to white
        image[:] = 255
        print(f"{imagepath} -> No circles (iris) found.")
        success = False
        # cv2.imshow("Image", image)
        # Wait for a key press (blocks execution)
        # cv2.waitKey(0)

        # Modify the return statement to ensure a tuple with three elements is always returned
        return image, success


# REMOVE REFLECTION FUNCTION


def remove_reflection(image) -> np.ndarray | None:
    try:
        # Threshold the image to create a mask of the reflection
        ret, mask = cv2.threshold(image, 150, 255, cv2.THRESH_BINARY)

        # Apply dilation to the mask to fill in gaps in the reflection
        kernel = np.ones((5, 5), np.uint8)
        dilation = cv2.dilate(mask, kernel, iterations=1)

        # Use inpainting to remove the reflection based on the dilation
        image_rr = cv2.inpaint(image, dilation, 5, cv2.INPAINT_TELEA)

        return image_rr

    except Exception as e:
        print("Error:", e)
        return None

# RUBBER SHEET MODEL GENERATOR FUNCTION


def generate_rubber_sheet_model(image) -> np.ndarray:

    q = np.arange(0.00, np.pi * 2, 0.01)
    inn = np.arange(0, int(image.shape[0] / 2), 1)

    cartisian_image = np.empty(shape=[inn.size, int(image.shape[1]), 3])
    m = interp1d([np.pi * 2, 0], [0, image.shape[1]])

    for r in inn:
        for t in q:
            polarX = int((r * np.cos(t)) + image.shape[1] / 2)
            polarY = int((r * np.sin(t)) + image.shape[0] / 2)
            try:
                cartisian_image[int(r)][int(m(t)-1)] = image[polarY][polarX]
            except Exception as e:
                print("Error:", e)

    return cartisian_image.astype("uint8")


def process_images(datas: list[tuple[typing.Any, str]]) -> tuple[list, list[str]]:

    processed_images: list = []
    processed_labels: list[str] = []

    for data in datas:

        image, label = data

        image_daugman = generate_rubber_sheet_model(image)

        if image_daugman is not None:
            processed_images.append(image_daugman)
            processed_labels.append(label)

        else:
            print(f"Failed to generate Daugman for image: {label}")

    return processed_images, processed_labels


def extract_features(datas: list[tuple[typing.Any, str]]) -> tuple[list[list], list[str]]:
    features: list[list] = []
    feature_labels: list[str] = []

    for data in datas:
        image, label = data
        feature = feature_extraction(image)

        if feature is []:
            continue

        features.append(feature)
        feature_labels.append(label)

    return features, feature_labels


def feature_extraction(img) -> list:
    features = []
    try:
        ccoeffs = pywt.dwt2(img[:, :, 0], 'haar')
    except Exception as e:
        return []

    LL, (LH, HL, HH) = ccoeffs
    for coef in [LL, LH, HL, HH]:
        features.append(np.mean(coef))
        features.append(np.std(coef))
        features.append(np.max(coef))
        features.append(np.min(coef))
        features.append(np.median(coef))

    titles = ['Approximation (LL)', 'Horizontal Detail (LH)',
              'Vertical Detail (HL)', 'Diagonal Detail (HH)']
    images = [LL, LH, HL, HH]
    # Plot all DWT coefficients horizontally in a single graph
    plt.figure(figsize=(12, 4))  # Adjust the figure size as needed

    for i, (title, image) in enumerate(zip(titles, images), 1):
        plt.subplot(1, 4, i)  # Arrange subplots in a single row
        plt.imshow(image, cmap='gray')
        plt.title(title)
        plt.axis('off')

    plt.show()

    return features

# DETECT IRIS FUNCTION
# OBSOLETE - Detect Iris using Iris Cascade


def detect_iris(eye_images, display):
    eye_num_2 = 0
    eyes_num = 0
    # explain how this works in presentation
    eye_cascade = cv2.CascadeClassifier('haarcascade_iris.xml')
    for eye_image in eye_images:
        (image, image_id, label) = eye_image
        image_id += 1
        eyes = eye_cascade.detectMultiScale(image, 1.1, 0)

        if len(eyes) > 1:  # idk what is happening
            eyes_num = eyes_num + 1
            maxium_area = -3

        for (x, y, width, height) in eyes:
            area = width * height

            if area > maxium_area:
                maxium_area = area
                maxium_width = width
                point_x = x
                point_y = y
                maxium_height = height

        image_unboxed = image.copy()

        image_cropped = image_unboxed[point_y:point_y + maxium_height,
                                      point_x:point_x + maxium_width,]

        image_boxed = cv2.rectangle(
            image,
            (point_x, point_y),
            (point_x + maxium_width, point_y + maxium_height),
            (255, 0, 0),
            2,
        )

        cv2.imwrite(
            'Processed/'+str(label) + '.' + str(image_id) + '.Iris' + '.bmp',
            image_cropped
        )

    print("iris image preprocessing done")

    if (display):
        fig, axes = plot.subplots(1, 3, figsize=(12, 5))

        axes[0].imshow(image_unboxed)
        axes[0].set_title('Original Image')
        axes[0].axis('off')  # Hide axes for cleaner presentation

        axes[1].imshow(image_boxed)
        axes[1].set_title('Iris Detection')
        axes[1].axis('off')

        axes[2].imshow(image_cropped)
        axes[2].set_title('Cropped Image')
        axes[2].axis('off')

        plot.tight_layout()
        plot.show()

    print("total_eyes_found = ", eyes_num)
    print("total_eyes_found 2 = ", eye_num_2)
    print("total images: ", len(eye_images))

# Parse iris dataset and load data


def load_data():
    eye_images = []
    labels = []

    base_directory = 'Dataset/VISA_Iris/VISA_Iris'

    for path in glob.iglob(base_directory + '/*'):
        foldername = os.path.basename(path)
        label = foldername
        print('Label:', label)
        image_id = 0

        # Process Left Eye
        for image_path in glob.iglob(path + '/L/*'):
            image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            image = cv2.resize(image, (400, 300))
            eye_images.append(image)  # Add image to features
            labels.append(label)  # Add label to labels
            image_id += 1

        print('Left eye count:', image_id)

        # Process Right Eye
        for image_path in glob.iglob(path + '/R/*'):
            image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            image = cv2.resize(image, (400, 300))
            eye_images.append(image)  # Add image to features
            labels.append(label + '-right')  # Add label to labels
            image_id += 1

        print('Right eye count:', image_id)

    print('Total iris images:', len(eye_images))
    return eye_images, labels


def split_data(
    features,
    labels,
    test_size: float = 0.2,
    train_directory: str = 'Iris_Output/Iris_Output_Split_Train',
    test_directory: str = 'Iris_Output/Iris_Output_Split_Test',
) -> tuple[any, any, any, any]:
    # Clear / Create directories
    if not os.path.exists(train_directory):
        os.makedirs(train_directory)

    if not os.path.exists(test_directory):
        os.makedirs(test_directory)

    # Split the data into training and testing sets
    x_train, x_test, y_train, y_test = train_test_split(
        features, labels,
        test_size=test_size,
        random_state=42,
    )

    # Save training data
    np.save(os.path.join(train_directory, 'X_train.npy'), x_train)
    np.save(os.path.join(train_directory, 'y_train.npy'), y_train)

    # Save testing data
    np.save(os.path.join(test_directory, 'X_test.npy'), x_test)
    np.save(os.path.join(test_directory, 'y_test.npy'), y_test)

    # Print the sizes of the training and testing sets
    print("Training set size:", len(x_train))
    print("Testing set size:", len(x_test))

    # # Save train data
    # for i, (feature, label) in enumerate(zip(x_train, y_train)):
    #     label_dir = os.path.join(train_directory, label)
    #     if not os.path.exists(label_dir):
    #         os.makedirs(label_dir)
    #     cv2.imwrite(os.path.join(label_dir, f'image_{i}.bmp'), feature)

    # # Save test data
    # for i, (feature, label) in enumerate(zip(x_test, y_test)):
    #     label_dir = os.path.join(test_directory, label)
    #     if not os.path.exists(label_dir):
    #         os.makedirs(label_dir)
    #     cv2.imwrite(os.path.join(label_dir, f'image_{i}.bmp'), feature)

    return x_train, x_test, y_train, y_test
