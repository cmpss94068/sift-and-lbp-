# Lint as: python3
# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Example using TF Lite to detect objects in a given image."""

import argparse
import time
import pandas as pd
import glob

from PIL import Image
from PIL import ImageDraw

import detect
import tflite_runtime.interpreter as tflite
import platform

EDGETPU_SHARED_LIB = {
  'Linux': 'libedgetpu.so.1',
  'Darwin': 'libedgetpu.1.dylib',
  'Windows': 'edgetpu.dll'
}[platform.system()]


def load_labels(path, encoding='utf-8'):
  """Loads labels from file (with or without index numbers).
  Args:
    path: path to label file.
    encoding: label file encoding.
  Returns:
    Dictionary mapping indices to labels.
  """
  with open(path, 'r', encoding=encoding) as f:
    lines = f.readlines()
    if not lines:
      return {}

    if lines[0].split(' ', maxsplit=1)[0].isdigit():
      pairs = [line.split(' ', maxsplit=1) for line in lines]
      return {int(index): label.strip() for index, label in pairs}
    else:
      return {index: line.strip() for index, line in enumerate(lines)}


def make_interpreter(model_file):
  model_file, *device = model_file.split('@')
  return tflite.Interpreter(
      model_path=model_file
      )


def draw_objects(draw, objs, labels):
  """Draws the bounding box and label for each object."""
  for obj in objs:
    bbox = obj.bbox
    draw.rectangle([(bbox.xmin, bbox.ymin), (bbox.xmax, bbox.ymax)],
                   outline='red')
    draw.text((bbox.xmin + 10, bbox.ymin + 10),
              '%s\n%.2f' % (labels.get(obj.id, obj.id), obj.score),
              fill='red')


def main():
  parser = argparse.ArgumentParser(
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument('-m', '--model', required=True,
                      help='File path of .tflite file.')
  parser.add_argument('-i', '--input',
                      help='File path of image to process.')
  parser.add_argument('-l', '--labels',
                      help='File path of labels file.')
  parser.add_argument('-t', '--threshold', type=float, default=0.4,
                      help='Score threshold for detected objects.')
  parser.add_argument('-o', '--output',
                      help='File path for the result image with annotations')
  parser.add_argument('-c', '--count', type=int, default=5,
                      help='Number of times to run inference')
  args = parser.parse_args()

  labels = load_labels(args.labels) if args.labels else {}
  interpreter = make_interpreter(args.model)
  interpreter.allocate_tensors()
  img_path = 'test_images/*.jpg'
  img_name = glob.glob(img_path)
  img_n = []
  img_id = []
  img_x = []
  img_y = []
  img_w = []
  img_h = []
  img_score = []
  img_csv = {}
  i = 0
  print(img_name[253])
  for img in img_name:
      image = Image.open(img)
      scale = detect.set_input(interpreter, image.size,
                               lambda size: image.resize(size, Image.ANTIALIAS))

      print('----INFERENCE TIME----')
      print('Note: The first inference is slow because it includes',
            'loading the model into Edge TPU memory.')
      for _ in range(args.count):
          start = time.perf_counter()
          interpreter.invoke()
          inference_time = time.perf_counter() - start
          objs = detect.get_output(interpreter, args.threshold, scale)
          print('%.2f ms' % (inference_time * 1000))

      print('-------RESULTS--------')
      if not objs:
         print('No objects detected')

      for obj in objs:
          print(labels.get(obj.id, obj.id))
          print('  id:    ', obj.id)
          print('  score: ', obj.score)
          print('  bbox:  ', obj.bbox)
          w = obj.bbox[2]-obj.bbox[0]
          h = obj.bbox[3]-obj.bbox[1]
          print('W:',w)
          print('H:',h)
          img_n.append(img)
          img_id.append(obj.id)
          img_x.append(obj.bbox[0])
          img_y.append(obj.bbox[1])
          img_w.append(w)
          img_h.append(h)
          img_score.append(obj.score)
      print(i)

      if args.output:
         image = image.convert('RGB')
         draw_objects(ImageDraw.Draw(image), objs, labels)
         image.save(args.output)
         image.show()
      i += 1
  for i in range(len(img_x)):
      img_dict = {
              "image_filename": img_n[i],
              "label_id": img_id,
              "x": img_x,
              "y": img_y,
              "w": img_w,
              "h": img_h,
              "confidence": img_score
              }
      img_csv.update(img_dict)

  img_csv.to_csv('test.csv')

if __name__ == '__main__':
  main()
