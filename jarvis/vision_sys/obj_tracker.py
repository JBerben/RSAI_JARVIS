from scipy.spatial import distance as dist
from collections import OrderedDict
import numpy as np
import pandas as pd

# df = pd.DataFrame(data={"Price":[4, 7, 9, 12], "Volume":[125, 139, 154, 167]})


class CentroidTracker:

	def __init__(self, roi: "(l, t, w, h) tuple", img_dims, max_obj_frames_lost):
		"""
		:param roi: a 4-tuple (left, top, width, height) containing info abt the pos and dims of the roi (screen px coords)
		e.g. roi = (8, 31, 783, 560) if wndw set using the def settings (0, 0, 800, 600)
		:param max_obj_frames_lost: This is the max # of traj_frames_dataset an obj (which is being tracked) is allowed to
		go "missing" for until it is permanently deleted from the tracking "container"/"watchlist" ....
		"""
		#
		# self.next_obj_id : A counter used to assign unique IDs to each object. In the case that an object leaves the frame
		# and does not come back for max_obj_frames_lost traj_frames_dataset, a new (next) object ID would be assigned.
		# self.obj_centroids : A dictionary consisting of object IDs and object centroids (in frame coords) key/value pairs.
		# E.g.: self.obj_centroids -> {1: np.array([1, 2]), 2:np..array([4, 3]), 3:np..array([6, 2])}
		# he object ID as the key and the obj frame centroid, (fx_c, fy_C)
		# self.obj_frames_lost : Maintains number of consecutive traj_frames_dataset (value) a particular object ID (key) has been marked as “lost”for
		# :param max_obj_frames_lost: The number of consecutive traj_frames_dataset an object is allowed to be marked as “lost/obj_frames_lost” until we deregister the object.
		self.roi = roi
		self.img_dims = img_dims
		self.next_obj_id = 0
		self.obj_centroids = OrderedDict()
		self.obj_frames_lost = OrderedDict()
		self.obj_scores = OrderedDict()
		self.obj_cls_labels = OrderedDict()
		self.max_obj_frames_lost = max_obj_frames_lost

	def register(self, centroid: "list of [fx_c, fy_c]", score: "float", class_label: "int"):
		# when registering an object we use the next available object
		# ID to store the centroid
		self.obj_centroids[self.next_obj_id] = centroid
		self.obj_frames_lost[self.next_obj_id] = 0
		self.obj_scores[self.next_obj_id] = score
		self.obj_cls_labels[self.next_obj_id] = class_label
		self.next_obj_id += 1

	def deregister(self, objectID):
		"""
		Deletes the objectID in both the obj_centroids and obj_frames_lost dictionaries, respectively.
		:param objectID: int
		:return:
		"""
		# to deregister an object ID we delete the object ID from
		# both of our respective dictionaries
		del self.obj_centroids[objectID]
		del self.obj_frames_lost[objectID]
		del self.obj_scores[objectID]
		del self.obj_cls_labels[objectID]
	# del self.obj_frames_lost[objectID]

	def update_tracking(self, boxes_frame_centroids: "list of nested [pxx_c, pxy_C] lists",
	                    boxes_scores: "numpy array w/ shape (len())", boxes_class_labels: "numpy array w/ shape (len())"):
		# check to see if the list of input bounding box rectangles
		# is empty
		if len(boxes_frame_centroids) == 0:
			# loop over any existing tracked obj_centroids and mark them
			# as obj_frames_lost
			for objectID in list(self.obj_frames_lost.keys()):
				self.obj_frames_lost[objectID] += 1

				# if we have reached a maximum number of consecutive
				# traj_frames_dataset where a given object has been marked as
				# missing, deregister it
				if self.obj_frames_lost[objectID] > self.max_obj_frames_lost:
					self.deregister(objectID)

			# return early as there are no centroids or tracking info
			# to update_tracking
			return self.obj_centroids

		# initialize an array of input centroids for the current frame
		current_boxes_frame_centroids_array = np.zeros((len(boxes_frame_centroids), 2), dtype="int") # current_boxes_frame_centroids_array.shape -> (100, 2)

		# loop over the bounding box rectangles
		for (bbox_i_frame_centroid_idx, (fx_c_i, fy_c_i)) in enumerate(boxes_frame_centroids):
			current_boxes_frame_centroids_array[bbox_i_frame_centroid_idx] = (fx_c_i, fy_c_i)

		# if we are currently not tracking any obj_centroids take the input
		# centroids and register each of them
		if len(self.obj_centroids) == 0:
			# for bbox_i_frame_centroid_idx in range(0, len(current_boxes_frame_centroids_array)):
			for bbox_i_idx in range(0, len(current_boxes_frame_centroids_array)):
				# centroid, score, class_label
				bbox_i_centroid = current_boxes_frame_centroids_array[bbox_i_idx]
				bbox_i_score = boxes_scores[bbox_i_idx]
				bbox_i_class_label = boxes_class_labels[bbox_i_idx]
				self.register(bbox_i_centroid, bbox_i_score, bbox_i_class_label)

		# otherwise, are are currently tracking obj_centroids so we need to
		# try to match the input centroids to existing object
		# centroids
		else:
			# grab the set of object IDs and corresponding centroids
			objectIDs = list(self.obj_centroids.keys())
			objectCentroids = list(self.obj_centroids.values())

			# compute the distance between each pair of object
			# centroids and input centroids, respectively -- our
			# goal will be to match an input centroid to an existing
			# object centroid
			D = dist.cdist(np.array(objectCentroids), current_boxes_frame_centroids_array)

			# in order to perform this matching we must (1) find the
			# smallest value in each row and then (2) sort the row
			# indexes based on their minimum values so that the row
			# with the smallest value as at the *front* of the index
			# list
			rows = D.min(axis=1).argsort()

			# next, we perform a similar process on the columns by
			# finding the smallest value in each column and then
			# sorting using the previously computed row index list
			cols = D.argmin(axis=1)[rows]

			# in order to determine if we need to update_tracking, register,
			# or deregister an object we need to keep track of which
			# of the rows and column indexes we have already examined
			usedRows = set()
			usedCols = set()

			# loop over the combination of the (row, column) index
			# tuples
			for (row, col) in zip(rows, cols):
				# if we have already examined either the row or
				# column value before, ignore it
				# val
				if row in usedRows or col in usedCols:
					continue

				# otherwise, grab the object ID for the current row,
				# set its new centroid, and reset the obj_frames_lost
				# counter
				objectID = objectIDs[row]
				self.obj_centroids[objectID] = current_boxes_frame_centroids_array[col]
				# print(f"objectID: {objectID}")
				# print(f"current_boxes_frame_centroids_array[col]: {current_boxes_frame_centroids_array[col]}")
				# print(f"type(current_boxes_frame_centroids_array[col]): {type(current_boxes_frame_centroids_array[col])}")
				# print(f"boxes_frame_centroids: {boxes_frame_centroids}")
				# print(f"type(boxes_frame_centroids[0]): {type(boxes_frame_centroids[0])}")
				boxes_frame_centroids_array = np.array(boxes_frame_centroids)
				matching_id = np.where(boxes_frame_centroids_array == current_boxes_frame_centroids_array[col])
				bbox_i_new_centroid_list_format = current_boxes_frame_centroids_array[col].tolist()
				bbox_i_new_centroid_idx = boxes_frame_centroids.index(bbox_i_new_centroid_list_format)
				matching_id_idx = bbox_i_new_centroid_idx
				bbox_i_new_score = boxes_scores[matching_id_idx]
				bbox_i_new_class_label = boxes_class_labels[matching_id_idx]
				# print(f"matching_id_idx: {matching_id_idx}")
				# print(f"bbox_i_new_score: {bbox_i_new_score}")
				self.obj_scores[objectID] = bbox_i_new_score
				self.obj_cls_labels[objectID] = bbox_i_new_class_label
				self.obj_frames_lost[objectID] = 0

				# indicate that we have examined each of the row and
				# column indexes, respectively
				usedRows.add(row)
				usedCols.add(col)

			# compute both the row and column index we have NOT yet
			# examined
			unusedRows = set(range(0, D.shape[0])).difference(usedRows)
			unusedCols = set(range(0, D.shape[1])).difference(usedCols)

			# in the event that the number of object centroids is
			# equal or greater than the number of input centroids
			# we need to check and see if some of these obj_centroids have
			# potentially obj_frames_lost
			if D.shape[0] >= D.shape[1]:
				# loop over the unused row indexes
				for row in unusedRows:
					# grab the object ID for the corresponding row
					# index and increment the obj_frames_lost counter
					objectID = objectIDs[row]
					self.obj_frames_lost[objectID] += 1

					# check to see if the number of consecutive
					# traj_frames_dataset the object has been marked "obj_frames_lost"
					# for warrants deregistering the object
					if self.obj_frames_lost[objectID] > self.max_obj_frames_lost:
						self.deregister(objectID)

			# otherwise, if the number of input centroids is greater
			# than the number of existing object centroids we need to
			# register each new input centroid as a trackable object
			else:
				for col in unusedCols:
					bbox_i_centroid = current_boxes_frame_centroids_array[col]
					bbox_i_score = boxes_scores[col]
					bbox_i_class_label = boxes_class_labels[col]
					self.register(bbox_i_centroid, bbox_i_score, bbox_i_class_label)

		# return the set of trackable obj_centroids
		return self.obj_centroids

	def get_current_tracking_objs_centroids(self):
		"""
		:return: a collections.OrderedDict w/ detected obj ID/screen relative centroid pos coordinates as key/val pairs
		"""
		return self.obj_centroids

	def get_current_tracking_objects(self):
		objects_centroids = self.obj_centroids
		objects_scores = self.obj_scores
		objects_class_labels = self.obj_cls_labels
		tracked_objects_unique_ids = list(objects_centroids.keys())
		tracked_objs_metadata_dict = OrderedDict()
		for tracked_object_i_unique_id in tracked_objects_unique_ids:
			tracked_obj_i_centroid = objects_centroids[tracked_object_i_unique_id]
			tracked_obj_i_score = objects_scores[tracked_object_i_unique_id]
			tracked_obj_i_class_label = objects_class_labels[tracked_object_i_unique_id]
			tracked_objs_metadata_dict[tracked_object_i_unique_id] = [tracked_obj_i_centroid,
			                                                          tracked_obj_i_score,
			                                                          tracked_obj_i_class_label]
		return tracked_objs_metadata_dict

	def compute_objs_centroid_ds_vectors(self):
		frame_centre_x_coord = self.img_dims[0] // 2
		frame_centre_y_coord = self.img_dims[1] // 2
		objects_centroids = self.get_current_tracking_objects()
		tracked_objects_unique_ids = list(objects_centroids.keys())
		tracked_objs_metadata_dict = OrderedDict()
		for tracked_object_i_unique_id in tracked_objects_unique_ids:
			tracked_obj_i_centroid = objects_centroids[tracked_object_i_unique_id]
			print(f"tracked_obj_i_centroid[0] {tracked_obj_i_centroid[0]}")
			bbox_i_centroid_x_coord, bbox_i_centroid_y_coord = tracked_obj_i_centroid[0]
			if bbox_i_centroid_x_coord > frame_centre_x_coord:
				bbox_i_lrf_dx = bbox_i_centroid_x_coord - frame_centre_x_coord
			else:
				bbox_i_lrf_dx = bbox_i_centroid_x_coord - frame_centre_x_coord
			if bbox_i_centroid_y_coord > frame_centre_y_coord:
				bbox_i_lrf_dy = bbox_i_centroid_y_coord - frame_centre_y_coord
			else:
				bbox_i_lrf_dy = bbox_i_centroid_y_coord - frame_centre_y_coord
			tracked_objs_metadata_dict[tracked_object_i_unique_id] = [int(bbox_i_lrf_dx/65), int(bbox_i_lrf_dy//58)]
		return tracked_objs_metadata_dict

	def compute_lrf_ds_vectors(self):
		"""
		lrs: Local Reference Frame
		ds: Distance
		:return: a numpy.ndarray containing the local reference frame distance vectors of the detected objects
		"""
		frame_width, frame_height = self.roi[2], self.roi[3]
		obj_centroid_keys = list(self.obj_centroids.keys())
		obj_centroid_lrf_coords = list(self.obj_centroids.values())
		print(f"~~~~~type(obj_centroid_lrf_coords): {type(obj_centroid_lrf_coords)}")
		print(f"~~~~~obj_centroid_lrf_coords: {obj_centroid_lrf_coords}")
		frame_origin_coords = np.array([[int(frame_width/2), int(frame_height/2)]])
		obj_centroid_lrf_coords_array = np.array(obj_centroid_lrf_coords)
		# print(f"obj_centroid_lrf_coords_array.shape: {obj_centroid_lrf_coords_array.shape}")
		# print(f"frame_origin_coords.shape: {frame_origin_coords.shape}")
		# print(f"obj_centroid_lrf_coords_array: {obj_centroid_lrf_coords_array}")
		# print(f"frame_origin_coords: {frame_origin_coords}")
		obj_centroids_lrf_ds_vectors = np.array([obj_centroid_lrf_coords]) - frame_origin_coords
		obj_centroids_lrf_ds_vectors = obj_centroids_lrf_ds_vectors[0]
		return obj_centroids_lrf_ds_vectors
		
