# Copyright 2015 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

"""RNN helpers for TensorFlow models.


@@bidirectional_dynamic_rnn
@@dynamic_rnn
@@raw_rnn
@@static_rnn
@@static_state_saving_rnn
@@static_bidirectional_rnn
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from tensorflow.python.framework import constant_op
from tensorflow.python.framework import dtypes
from tensorflow.python.framework import ops
from tensorflow.python.framework import tensor_shape
from tensorflow.python.ops import array_ops
from tensorflow.python.ops import control_flow_ops
from tensorflow.python.ops import math_ops
from tensorflow.python.ops import rnn_cell_impl
from tensorflow.python.ops import tensor_array_ops
from tensorflow.python.ops import variable_scope as vs
from tensorflow.python.util import nest

#from tensorflow.contrib.rnn.python.ops import core_rnn_cell


# pylint: disable=protected-access
_concat = rnn_cell_impl._concat
_like_rnncell = rnn_cell_impl.assert_like_rnncell
# pylint: enable=protected-access


def _transpose_batch_time(x):
  """Transpose the batch and time dimensions of a Tensor.

  Retains as much of the static shape information as possible.

  Args:
    x: A tensor of rank 2 or higher.

  Returns:
    x transposed along the first two dimensions.

  Raises:
    ValueError: if `x` is rank 1 or lower.
  """
  x_static_shape = x.get_shape()
  if x_static_shape.ndims is not None and x_static_shape.ndims < 2:
    raise ValueError(
        "Expected input tensor %s to have rank at least 2, but saw shape: %s" %
        (x, x_static_shape))
  x_rank = array_ops.rank(x)
  x_t = array_ops.transpose(
      x, array_ops.concat(
          ([1, 0], math_ops.range(2, x_rank)), axis=0))
  x_t.set_shape(
      tensor_shape.TensorShape([
          x_static_shape[1], x_static_shape[0]
      ]).concatenate(x_static_shape[2:]))
  return x_t


def _best_effort_input_batch_size(flat_input):
  """Get static input batch size if available, with fallback to the dynamic one.

  Args:
    flat_input: An iterable of time major input Tensors of shape [max_time,
      batch_size, ...]. All inputs should have compatible batch sizes.

  Returns:
    The batch size in Python integer if available, or a scalar Tensor otherwise.

  Raises:
    ValueError: if there is any input with an invalid shape.
  """
  for input_ in flat_input:
    shape = input_.shape
    if shape.ndims is None:
      continue
    if shape.ndims < 2:
      raise ValueError(
          "Expected input tensor %s to have rank at least 2" % input_)
    batch_size = shape[1]
    if batch_size is not None:
      return batch_size
  # Fallback to the dynamic batch size of the first input.
  return array_ops.shape(flat_input[0])[1]


def _infer_state_dtype(explicit_dtype, state):
  """Infer the dtype of an RNN state.

  Args:
    explicit_dtype: explicitly declared dtype or None.
    state: RNN's hidden state. Must be a Tensor or a nested iterable containing
      Tensors.

  Returns:
    dtype: inferred dtype of hidden state.

  Raises:
    ValueError: if `state` has heterogeneous dtypes or is empty.
  """
  if explicit_dtype is not None:
    return explicit_dtype
  elif nest.is_sequence(state):
    inferred_dtypes = [element.dtype for element in nest.flatten(state)]
    if not inferred_dtypes:
      raise ValueError("Unable to infer dtype from empty state.")
    all_same = all([x == inferred_dtypes[0] for x in inferred_dtypes])
    if not all_same:
      raise ValueError(
          "State has tensors of different inferred_dtypes. Unable to infer a "
          "single representative dtype.")
    return inferred_dtypes[0]
  else:
    return state.dtype


# pylint: disable=unused-argument
def _rnn_step(
    time, sequence_length, min_sequence_length, max_sequence_length,
    zero_output, state, call_cell, state_size, skip_conditionals=False):
  """Calculate one step of a dynamic RNN minibatch.

  Returns an (output, state) pair conditioned on the sequence_lengths.
  When skip_conditionals=False, the pseudocode is something like:

  if t >= max_sequence_length:
    return (zero_output, state)
  if t < min_sequence_length:
    return call_cell()

  # Selectively output zeros or output, old state or new state depending
  # on if we've finished calculating each row.
  new_output, new_state = call_cell()
  final_output = np.vstack([
    zero_output if time >= sequence_lengths[r] else new_output_r
    for r, new_output_r in enumerate(new_output)
  ])
  final_state = np.vstack([
    state[r] if time >= sequence_lengths[r] else new_state_r
    for r, new_state_r in enumerate(new_state)
  ])
  return (final_output, final_state)

  Args:
    time: Python int, the current time step
    sequence_length: int32 `Tensor` vector of size [batch_size]
    min_sequence_length: int32 `Tensor` scalar, min of sequence_length
    max_sequence_length: int32 `Tensor` scalar, max of sequence_length
    zero_output: `Tensor` vector of shape [output_size]
    state: Either a single `Tensor` matrix of shape `[batch_size, state_size]`,
      or a list/tuple of such tensors.
    call_cell: lambda returning tuple of (new_output, new_state) where
      new_output is a `Tensor` matrix of shape `[batch_size, output_size]`.
      new_state is a `Tensor` matrix of shape `[batch_size, state_size]`.
    state_size: The `cell.state_size` associated with the state.
    skip_conditionals: Python bool, whether to skip using the conditional
      calculations.  This is useful for `dynamic_rnn`, where the input tensor
      matches `max_sequence_length`, and using conditionals just slows
      everything down.

  Returns:
    A tuple of (`final_output`, `final_state`) as given by the pseudocode above:
      final_output is a `Tensor` matrix of shape [batch_size, output_size]
      final_state is either a single `Tensor` matrix, or a tuple of such
        matrices (matching length and shapes of input `state`).

  Raises:
    ValueError: If the cell returns a state tuple whose length does not match
      that returned by `state_size`.
  """

  # Convert state to a list for ease of use
  flat_state = nest.flatten(state)
  flat_zero_output = nest.flatten(zero_output)

  def _copy_one_through(output, new_output):
    # If the state contains a scalar value we simply pass it through.
    if output.shape.ndims == 0:
      return new_output
    copy_cond = (time >= sequence_length)
    with ops.colocate_with(new_output):
      return array_ops.where(copy_cond, output, new_output)

  def _copy_some_through(flat_new_output, flat_new_state):
    # Use broadcasting select to determine which values should get
    # the previous state & zero output, and which values should get
    # a calculated state & output.
    flat_new_output = [
        _copy_one_through(zero_output, new_output)
        for zero_output, new_output in zip(flat_zero_output, flat_new_output)]
    flat_new_state = [
        _copy_one_through(state, new_state)
        for state, new_state in zip(flat_state, flat_new_state)]
    return flat_new_output + flat_new_state

  def _maybe_copy_some_through():
    """Run RNN step.  Pass through either no or some past state."""
    new_output, new_state = call_cell()

    nest.assert_same_structure(state, new_state)

    flat_new_state = nest.flatten(new_state)
    flat_new_output = nest.flatten(new_output)
    return control_flow_ops.cond(
        # if t < min_seq_len: calculate and return everything
        time < min_sequence_length, lambda: flat_new_output + flat_new_state,
        # else copy some of it through
        lambda: _copy_some_through(flat_new_output, flat_new_state))

  # TODO(ebrevdo): skipping these conditionals may cause a slowdown,
  # but benefits from removing cond() and its gradient.  We should
  # profile with and without this switch here.
  if skip_conditionals:
    # Instead of using conditionals, perform the selective copy at all time
    # steps.  This is faster when max_seq_len is equal to the number of unrolls
    # (which is typical for dynamic_rnn).
    new_output, new_state = call_cell()
    nest.assert_same_structure(state, new_state)
    new_state = nest.flatten(new_state)
    new_output = nest.flatten(new_output)
    final_output_and_state = _copy_some_through(new_output, new_state)
  else:
    empty_update = lambda: flat_zero_output + flat_state
    final_output_and_state = control_flow_ops.cond(
        # if t >= max_seq_len: copy all state through, output zeros
        time >= max_sequence_length, empty_update,
        # otherwise calculation is required: copy some or all of it through
        _maybe_copy_some_through)

  if len(final_output_and_state) != len(flat_zero_output) + len(flat_state):
    raise ValueError("Internal error: state and output were not concatenated "
                     "correctly.")
  final_output = final_output_and_state[:len(flat_zero_output)]
  final_state = final_output_and_state[len(flat_zero_output):]

  for output, flat_output in zip(final_output, flat_zero_output):
    output.set_shape(flat_output.get_shape())
  for substate, flat_substate in zip(final_state, flat_state):
    substate.set_shape(flat_substate.get_shape())

  final_output = nest.pack_sequence_as(
      structure=zero_output, flat_sequence=final_output)
  final_state = nest.pack_sequence_as(
      structure=state, flat_sequence=final_state)

  return final_output, final_state


def _reverse_seq(input_seq, lengths):
  """Reverse a list of Tensors up to specified lengths.

  Args:
    input_seq: Sequence of seq_len tensors of dimension (batch_size, n_features)
               or nested tuples of tensors.
    lengths:   A `Tensor` of dimension batch_size, containing lengths for each
               sequence in the batch. If "None" is specified, simply reverses
               the list.

  Returns:
    time-reversed sequence
  """
  if lengths is None:
    return list(reversed(input_seq))

  flat_input_seq = tuple(nest.flatten(input_) for input_ in input_seq)

  flat_results = [[] for _ in range(len(input_seq))]
  for sequence in zip(*flat_input_seq):
    input_shape = tensor_shape.unknown_shape(
        ndims=sequence[0].get_shape().ndims)
    for input_ in sequence:
      input_shape.merge_with(input_.get_shape())
      input_.set_shape(input_shape)

    # Join into (time, batch_size, depth)
    s_joined = array_ops.stack(sequence)

    # Reverse along dimension 0
    s_reversed = array_ops.reverse_sequence(s_joined, lengths, 0, 1)
    # Split again into list
    result = array_ops.unstack(s_reversed)
    for r, flat_result in zip(result, flat_results):
      r.set_shape(input_shape)
      flat_result.append(r)

  results = [nest.pack_sequence_as(structure=input_, flat_sequence=flat_result)
             for input_, flat_result in zip(input_seq, flat_results)]
  return results


def bidirectional_dynamic_rnn(cell_fw, cell_bw, inputs, sequence_length=None,
                              initial_state_fw=None, initial_state_bw=None,
                              dtype=None, parallel_iterations=None,
                              swap_memory=False, time_major=False, scope=None):
  """Creates a dynamic version of bidirectional recurrent neural network.

  Takes input and builds independent forward and backward RNNs. The input_size
  of forward and backward cell must match. The initial state for both directions
  is zero by default (but can be set optionally) and no intermediate states are
  ever returned -- the network is fully unrolled for the given (passed in)
  length(s) of the sequence(s) or completely unrolled if length(s) is not
  given.

  Args:
    cell_fw: An instance of RNNCell, to be used for forward direction.
    cell_bw: An instance of RNNCell, to be used for backward direction.
    inputs: The RNN inputs.
      If time_major == False (default), this must be a tensor of shape:
        `[batch_size, max_time, ...]`, or a nested tuple of such elements.
      If time_major == True, this must be a tensor of shape:
        `[max_time, batch_size, ...]`, or a nested tuple of such elements.
    sequence_length: (optional) An int32/int64 vector, size `[batch_size]`,
      containing the actual lengths for each of the sequences in the batch.
      If not provided, all batch entries are assumed to be full sequences; and
      time reversal is applied from time `0` to `max_time` for each sequence.
    initial_state_fw: (optional) An initial state for the forward RNN.
      This must be a tensor of appropriate type and shape
      `[batch_size, cell_fw.state_size]`.
      If `cell_fw.state_size` is a tuple, this should be a tuple of
      tensors having shapes `[batch_size, s] for s in cell_fw.state_size`.
    initial_state_bw: (optional) Same as for `initial_state_fw`, but using
      the corresponding properties of `cell_bw`.
    dtype: (optional) The data type for the initial states and expected output.
      Required if initial_states are not provided or RNN states have a
      heterogeneous dtype.
    parallel_iterations: (Default: 32).  The number of iterations to run in
      parallel.  Those operations which do not have any temporal dependency
      and can be run in parallel, will be.  This parameter trades off
      time for space.  Values >> 1 use more memory but take less time,
      while smaller values use less memory but computations take longer.
    swap_memory: Transparently swap the tensors produced in forward inference
      but needed for back prop from GPU to CPU.  This allows training RNNs
      which would typically not fit on a single GPU, with very minimal (or no)
      performance penalty.
    time_major: The shape format of the `inputs` and `outputs` Tensors.
      If true, these `Tensors` must be shaped `[max_time, batch_size, depth]`.
      If false, these `Tensors` must be shaped `[batch_size, max_time, depth]`.
      Using `time_major = True` is a bit more efficient because it avoids
      transposes at the beginning and end of the RNN calculation.  However,
      most TensorFlow data is batch-major, so by default this function
      accepts input and emits output in batch-major form.
    scope: VariableScope for the created subgraph; defaults to
      "bidirectional_rnn"

  Returns:
    A tuple (outputs, output_states) where:
      outputs: A tuple (output_fw, output_bw) containing the forward and
        the backward rnn output `Tensor`.
        If time_major == False (default),
          output_fw will be a `Tensor` shaped:
          `[batch_size, max_time, cell_fw.output_size]`
          and output_bw will be a `Tensor` shaped:
          `[batch_size, max_time, cell_bw.output_size]`.
        If time_major == True,
          output_fw will be a `Tensor` shaped:
          `[max_time, batch_size, cell_fw.output_size]`
          and output_bw will be a `Tensor` shaped:
          `[max_time, batch_size, cell_bw.output_size]`.
        It returns a tuple instead of a single concatenated `Tensor`, unlike
        in the `bidirectional_rnn`. If the concatenated one is preferred,
        the forward and backward outputs can be concatenated as
        `tf.concat(outputs, 2)`.
      output_states: A tuple (output_state_fw, output_state_bw) containing
        the forward and the backward final states of bidirectional rnn.

  Raises:
    TypeError: If `cell_fw` or `cell_bw` is not an instance of `RNNCell`.
  """

  _like_rnncell("cell_fw must be an instance of RNNCell", cell_fw)
  _like_rnncell("cell_bw must be an instance of RNNCell", cell_bw)

  with vs.variable_scope(scope or "bidirectional_rnn"):
    # Forward direction
    with vs.variable_scope("fw") as fw_scope:
      output_fw, output_state_fw = dynamic_rnn(
          cell=cell_fw, inputs=inputs, sequence_length=sequence_length,
          initial_state=initial_state_fw, dtype=dtype,
          parallel_iterations=parallel_iterations, swap_memory=swap_memory,
          time_major=time_major, scope=fw_scope)

    # Backward direction
    if not time_major:
      time_dim = 1
      batch_dim = 0
    else:
      time_dim = 0
      batch_dim = 1

    def _reverse(input_, seq_lengths, seq_dim, batch_dim):
      if seq_lengths is not None:
        return array_ops.reverse_sequence(
            input=input_, seq_lengths=seq_lengths,
            seq_dim=seq_dim, batch_dim=batch_dim)
      else:
        return array_ops.reverse(input_, axis=[seq_dim])

    with vs.variable_scope("bw") as bw_scope:
      inputs_reverse = _reverse(
          inputs, seq_lengths=sequence_length,
          seq_dim=time_dim, batch_dim=batch_dim)
      tmp, output_state_bw = dynamic_rnn(
          cell=cell_bw, inputs=inputs_reverse, sequence_length=sequence_length,
          initial_state=initial_state_bw, dtype=dtype,
          parallel_iterations=parallel_iterations, swap_memory=swap_memory,
          time_major=time_major, scope=bw_scope)

  output_bw = _reverse(
      tmp, seq_lengths=sequence_length,
      seq_dim=time_dim, batch_dim=batch_dim)

  outputs = (output_fw, output_bw)
  output_states = (output_state_fw, output_state_bw)

  return (outputs, output_states)


def dynamic_rnn(cell, inputs, att_scores=None, sequence_length=None, initial_state=None,
                dtype=None, parallel_iterations=None, swap_memory=False,
                time_major=False, scope=None):
  """Creates a recurrent neural network specified by RNNCell `cell`.

  Performs fully dynamic unrolling of `inputs`.

  Example:

  ```python
  # create a BasicRNNCell
  rnn_cell = tf.nn.rnn_cell.BasicRNNCell(hidden_size)

  # 'outputs' is a tensor of shape [batch_size, max_time, cell_state_size]

  # defining initial state
  initial_state = rnn_cell.zero_state(batch_size, dtype=tf.float32)

  # 'state' is a tensor of shape [batch_size, cell_state_size]
  outputs, state = tf.nn.dynamic_rnn(rnn_cell, input_data,
                                     initial_state=initial_state,
                                     dtype=tf.float32)
  ```

  ```python
  # create 2 LSTMCells
  rnn_layers = [tf.nn.rnn_cell.LSTMCell(size) for size in [128, 256]]

  # create a RNN cell composed sequentially of a number of RNNCells
  multi_rnn_cell = tf.nn.rnn_cell.MultiRNNCell(rnn_layers)

  # 'outputs' is a tensor of shape [batch_size, max_time, 256]
  # 'state' is a N-tuple where N is the number of LSTMCells containing a
  # tf.contrib.rnn.LSTMStateTuple for each cell
  outputs, state = tf.nn.dynamic_rnn(cell=multi_rnn_cell,
                                     inputs=data,
                                     dtype=tf.float32)
  ```


  Args:
    cell: An instance of RNNCell.
    inputs: The RNN inputs.
      If `time_major == False` (default), this must be a `Tensor` of shape:
        `[batch_size, max_time, ...]`, or a nested tuple of such
        elements.
      If `time_major == True`, this must be a `Tensor` of shape:
        `[max_time, batch_size, ...]`, or a nested tuple of such
        elements.
      This may also be a (possibly nested) tuple of Tensors satisfying
      this property.  The first two dimensions must match across all the inputs,
      but otherwise the ranks and other shape components may differ.
      In this case, input to `cell` at each time-step will replicate the
      structure of these tuples, except for the time dimension (from which the
      time is taken).
      The input to `cell` at each time step will be a `Tensor` or (possibly
      nested) tuple of Tensors each with dimensions `[batch_size, ...]`.
    sequence_length: (optional) An int32/int64 vector sized `[batch_size]`.
      Used to copy-through state and zero-out outputs when past a batch
      element's sequence length.  So it's more for correctness than performance.
    initial_state: (optional) An initial state for the RNN.
      If `cell.state_size` is an integer, this must be
      a `Tensor` of appropriate type and shape `[batch_size, cell.state_size]`.
      If `cell.state_size` is a tuple, this should be a tuple of
      tensors having shapes `[batch_size, s] for s in cell.state_size`.
    dtype: (optional) The data type for the initial state and expected output.
      Required if initial_state is not provided or RNN state has a heterogeneous
      dtype.
    parallel_iterations: (Default: 32).  The number of iterations to run in
      parallel.  Those operations which do not have any temporal dependency
      and can be run in parallel, will be.  This parameter trades off
      time for space.  Values >> 1 use more memory but take less time,
      while smaller values use less memory but computations take longer.
    swap_memory: Transparently swap the tensors produced in forward inference
      but needed for back prop from GPU to CPU.  This allows training RNNs
      which would typically not fit on a single GPU, with very minimal (or no)
      performance penalty.
    time_major: The shape format of the `inputs` and `outputs` Tensors.
      If true, these `Tensors` must be shaped `[max_time, batch_size, depth]`.
      If false, these `Tensors` must be shaped `[batch_size, max_time, depth]`.
      Using `time_major = True` is a bit more efficient because it avoids
      transposes at the beginning and end of the RNN calculation.  However,
      most TensorFlow data is batch-major, so by default this function
      accepts input and emits output in batch-major form.
    scope: VariableScope for the created subgraph; defaults to "rnn".

  Returns:
    A pair (outputs, state) where:

    outputs: The RNN output `Tensor`.

      If time_major == False (default), this will be a `Tensor` shaped:
        `[batch_size, max_time, cell.output_size]`.

      If time_major == True, this will be a `Tensor` shaped:
        `[max_time, batch_size, cell.output_size]`.

      Note, if `cell.output_size` is a (possibly nested) tuple of integers
      or `TensorShape` objects, then `outputs` will be a tuple having the
      same structure as `cell.output_size`, containing Tensors having shapes
      corresponding to the shape data in `cell.output_size`.

    state: The final state.  If `cell.state_size` is an int, this
      will be shaped `[batch_size, cell.state_size]`.  If it is a
      `TensorShape`, this will be shaped `[batch_size] + cell.state_size`.
      If it is a (possibly nested) tuple of ints or `TensorShape`, this will
      be a tuple having the corresponding shapes. If cells are `LSTMCells`
      `state` will be a tuple containing a `LSTMStateTuple` for each cell.

  Raises:
    TypeError: If `cell` is not an instance of RNNCell.
    ValueError: If inputs is None or an empty list.
  """
  _like_rnncell("cell must be an instance of RNNCell", cell)

  # By default, time_major==False and inputs are batch-major: shaped
  #   [batch, time, depth]
  # For internal calculations, we transpose to [time, batch, depth]
  flat_input = nest.flatten(inputs)

  if not time_major:
    # (B,T,D) => (T,B,D)
    flat_input = [ops.convert_to_tensor(input_) for input_ in flat_input]
    flat_input = tuple(_transpose_batch_time(input_) for input_ in flat_input)

  parallel_iterations = parallel_iterations or 32
  if sequence_length is not None:
    sequence_length = math_ops.to_int32(sequence_length)
    if sequence_length.get_shape().ndims not in (None, 1):
      raise ValueError(
          "sequence_length must be a vector of length batch_size, "
          "but saw shape: %s" % sequence_length.get_shape())
    sequence_length = array_ops.identity(  # Just to find it in the graph.
        sequence_length, name="sequence_length")

  # Create a new scope in which the caching device is either
  # determined by the parent scope, or is set to place the cached
  # Variable using the same placement as for the rest of the RNN.
  with vs.variable_scope(scope or "rnn") as varscope:
    if varscope.caching_device is None:
      varscope.set_caching_device(lambda op: op.device)
    batch_size = _best_effort_input_batch_size(flat_input)

    if initial_state is not None:
      state = initial_state
    else:
      if not dtype:
        raise ValueError("If there is no initial_state, you must give a dtype.")
      state = cell.zero_state(batch_size, dtype)

    def _assert_has_shape(x, shape):
      x_shape = array_ops.shape(x)
      packed_shape = array_ops.stack(shape)
      return control_flow_ops.Assert(
          math_ops.reduce_all(math_ops.equal(x_shape, packed_shape)),
          ["Expected shape for Tensor %s is " % x.name,
           packed_shape, " but saw shape: ", x_shape])

    if sequence_length is not None:
      # Perform some shape validation
      with ops.control_dependencies(
          [_assert_has_shape(sequence_length, [batch_size])]):
        sequence_length = array_ops.identity(
            sequence_length, name="CheckSeqLen")

    inputs = nest.pack_sequence_as(structure=inputs, flat_sequence=flat_input)

    (outputs, final_state) = _dynamic_rnn_loop(
        cell,
        inputs,
        state,
        parallel_iterations=parallel_iterations,
        swap_memory=swap_memory,
        att_scores = att_scores,
        sequence_length=sequence_length,
        dtype=dtype)

    # Outputs of _dynamic_rnn_loop are always shaped [time, batch, depth].
    # If we are performing batch-major calculations, transpose output back
    # to shape [batch, time, depth]
    if not time_major:
      # (T,B,D) => (B,T,D)
      outputs = nest.map_structure(_transpose_batch_time, outputs)

    return (outputs, final_state)


def _dynamic_rnn_loop(cell,
                      inputs,
                      initial_state,
                      parallel_iterations,
                      swap_memory,
                      att_scores = None,
                      sequence_length=None,
                      dtype=None):
  """Internal implementation of Dynamic RNN.

  Args:
    cell: An instance of RNNCell.
    inputs: A `Tensor` of shape [time, batch_size, input_size], or a nested
      tuple of such elements.
    initial_state: A `Tensor` of shape `[batch_size, state_size]`, or if
      `cell.state_size` is a tuple, then this should be a tuple of
      tensors having shapes `[batch_size, s] for s in cell.state_size`.
    parallel_iterations: Positive Python int.
    swap_memory: A Python boolean
    sequence_length: (optional) An `int32` `Tensor` of shape [batch_size].
    dtype: (optional) Expected dtype of output. If not specified, inferred from
      initial_state.

  Returns:
    Tuple `(final_outputs, final_state)`.
    final_outputs:
      A `Tensor` of shape `[time, batch_size, cell.output_size]`.  If
      `cell.output_size` is a (possibly nested) tuple of ints or `TensorShape`
      objects, then this returns a (possibly nsted) tuple of Tensors matching
      the corresponding shapes.
    final_state:
      A `Tensor`, or possibly nested tuple of Tensors, matching in length
      and shapes to `initial_state`.

  Raises:
    ValueError: If the input depth cannot be inferred via shape inference
      from the inputs.
  """
  state = initial_state
  assert isinstance(parallel_iterations, int), "parallel_iterations must be int"

  state_size = cell.state_size

  flat_input = nest.flatten(inputs)
  flat_output_size = nest.flatten(cell.output_size)

  # Construct an initial output
  input_shape = array_ops.shape(flat_input[0])
  time_steps = input_shape[0]
  batch_size = _best_effort_input_batch_size(flat_input)

  inputs_got_shape = tuple(input_.get_shape().with_rank_at_least(3)
                           for input_ in flat_input)

  const_time_steps, const_batch_size = inputs_got_shape[0].as_list()[:2]

  for shape in inputs_got_shape:
    if not shape[2:].is_fully_defined():
      raise ValueError(
          "Input size (depth of inputs) must be accessible via shape inference,"
          " but saw value None.")
    got_time_steps = shape[0]
    got_batch_size = shape[1]
    if const_time_steps != got_time_steps:
      raise ValueError(
          "Time steps is not the same for all the elements in the input in a "
          "batch.")
    if const_batch_size != got_batch_size:
      raise ValueError(
          "Batch_size is not the same for all the elements in the input.")

  # Prepare dynamic conditional copying of state & output
  def _create_zero_arrays(size):
    size = _concat(batch_size, size)
    return array_ops.zeros(
        array_ops.stack(size), _infer_state_dtype(dtype, state))

  flat_zero_output = tuple(_create_zero_arrays(output)
                           for output in flat_output_size)
  zero_output = nest.pack_sequence_as(structure=cell.output_size,
                                      flat_sequence=flat_zero_output)

  if sequence_length is not None:
    min_sequence_length = math_ops.reduce_min(sequence_length)
    max_sequence_length = math_ops.reduce_max(sequence_length)

  time = array_ops.constant(0, dtype=dtypes.int32, name="time")

  with ops.name_scope("dynamic_rnn") as scope:
    base_name = scope

  def _create_ta(name, dtype):
    return tensor_array_ops.TensorArray(dtype=dtype,
                                        size=time_steps,
                                        tensor_array_name=base_name + name)

  output_ta = tuple(_create_ta("output_%d" % i,
                               _infer_state_dtype(dtype, state))
                    for i in range(len(flat_output_size)))
  input_ta = tuple(_create_ta("input_%d" % i, flat_input[i].dtype)
                   for i in range(len(flat_input)))

  input_ta = tuple(ta.unstack(input_)
                   for ta, input_ in zip(input_ta, flat_input))

  def _time_step(time, output_ta_t, state, att_scores=None):
    """Take a time step of the dynamic RNN.

    Args:
      time: int32 scalar Tensor.
      output_ta_t: List of `TensorArray`s that represent the output.
      state: nested tuple of vector tensors that represent the state.

    Returns:
      The tuple (time + 1, output_ta_t with updated flow, new_state).
    """

    input_t = tuple(ta.read(time) for ta in input_ta)
    # Restore some shape information
    for input_, shape in zip(input_t, inputs_got_shape):
      input_.set_shape(shape[1:])

    input_t = nest.pack_sequence_as(structure=inputs, flat_sequence=input_t)
    if att_scores is not None:
        att_score = att_scores[:, time, :]
        call_cell = lambda: cell(input_t, state, att_score)
    else:
        call_cell = lambda: cell(input_t, state)

    if sequence_length is not None:
      (output, new_state) = _rnn_step(
          time=time,
          sequence_length=sequence_length,
          min_sequence_length=min_sequence_length,
          max_sequence_length=max_sequence_length,
          zero_output=zero_output,
          state=state,
          call_cell=call_cell,
          state_size=state_size,
          skip_conditionals=True)
    else:
      (output, new_state) = call_cell()

    # Pack state if using state tuples
    output = nest.flatten(output)

    output_ta_t = tuple(
        ta.write(time, out) for ta, out in zip(output_ta_t, output))
    if att_scores is not None:
        return (time + 1, output_ta_t, new_state, att_scores)
    else:
        return (time + 1, output_ta_t, new_state)

  if att_scores is not None:  
      _, output_final_ta, final_state, _ = control_flow_ops.while_loop(
          cond=lambda time, *_: time < time_steps,
          body=_time_step,
          loop_vars=(time, output_ta, state, att_scores),
          parallel_iterations=parallel_iterations,
          swap_memory=swap_memory)
  else:
      _, output_final_ta, final_state = control_flow_ops.while_loop(
          cond=lambda time, *_: time < time_steps,
          body=_time_step,
          loop_vars=(time, output_ta, state),
          parallel_iterations=parallel_iterations,
          swap_memory=swap_memory)

  # Unpack final output if not using output tuples.
  final_outputs = tuple(ta.stack() for ta in output_final_ta)

  # Restore some shape information
  for output, output_size in zip(final_outputs, flat_output_size):
    shape = _concat(
        [const_time_steps, const_batch_size], output_size, static=True)
    output.set_shape(shape)

  final_outputs = nest.pack_sequence_as(
      structure=cell.output_size, flat_sequence=final_outputs)

  return (final_outputs, final_state)


def raw_rnn(cell, loop_fn,
            parallel_iterations=None, swap_memory=False, scope=None):
  """Creates an `RNN` specified by RNNCell `cell` and loop function `loop_fn`.

  **NOTE: This method is still in testing, and the API may change.**

  This function is a more primitive version of `dynamic_rnn` that provides
  more direct access to the inputs each iteration.  It also provides more
  control over when to start and finish reading the sequence, and
  what to emit for the output.

  For example, it can be used to implement the dynamic decoder of a seq2seq
  model.

  Instead of working with `Tensor` objects, most operations work with
  `TensorArray` objects directly.

  The operation of `raw_rnn`, in pseudo-code, is basically the following:

  ```python
  time = tf.constant(0, dtype=tf.int32)
  (finished, next_input, initial_state, _, loop_state) = loop_fn(
      time=time, cell_output=None, cell_state=None, loop_state=None)
  emit_ta = TensorArray(dynamic_size=True, dtype=initial_state.dtype)
  state = initial_state
  while not all(finished):
    (output, cell_state) = cell(next_input, state)
    (next_finished, next_input, next_state, emit, loop_state) = loop_fn(
        time=time + 1, cell_output=output, cell_state=cell_state,
        loop_state=loop_state)
    # Emit zeros and copy forward state for minibatch entries that are finished.
    state = tf.where(finished, state, next_state)
    emit = tf.where(finished, tf.zeros_like(emit), emit)
    emit_ta = emit_ta.write(time, emit)
    # If any new minibatch entries are marked as finished, mark these.
    finished = tf.logical_or(finished, next_finished)
    time += 1
  return (emit_ta, state, loop_state)
  ```

  with the additional properties that output and state may be (possibly nested)
  tuples, as determined by `cell.output_size` and `cell.state_size`, and
  as a result the final `state` and `emit_ta` may themselves be tuples.

  A simple implementation of `dynamic_rnn` via `raw_rnn` looks like this:

  ```python
  inputs = tf.placeholder(shape=(max_time, batch_size, input_depth),
                          dtype=tf.float32)
  sequence_length = tf.placeholder(shape=(batch_size,), dtype=tf.int32)
  inputs_ta = tf.TensorArray(dtype=tf.float32, size=max_time)
  inputs_ta = inputs_ta.unstack(inputs)

  cell = tf.contrib.rnn.LSTMCell(num_units)

  def loop_fn(time, cell_output, cell_state, loop_state):
    emit_output = cell_output  # == None for time == 0
    if cell_output is None:  # time == 0
      next_cell_state = cell.zero_state(batch_size, tf.float32)
    else:
      next_cell_state = cell_state
    elements_finished = (time >= sequence_length)
    finished = tf.reduce_all(elements_finished)
    next_input = tf.cond(
        finished,
        lambda: tf.zeros([batch_size, input_depth], dtype=tf.float32),
        lambda: inputs_ta.read(time))
    next_loop_state = None
    return (elements_finished, next_input, next_cell_state,
            emit_output, next_loop_state)

  outputs_ta, final_state, _ = raw_rnn(cell, loop_fn)
  outputs = outputs_ta.stack()
  ```

  Args:
    cell: An instance of RNNCell.
    loop_fn: A callable that takes inputs
      `(time, cell_output, cell_state, loop_state)`
      and returns the tuple
      `(finished, next_input, next_cell_state, emit_output, next_loop_state)`.
      Here `time` is an int32 scalar `Tensor`, `cell_output` is a
      `Tensor` or (possibly nested) tuple of tensors as determined by
      `cell.output_size`, and `cell_state` is a `Tensor`
      or (possibly nested) tuple of tensors, as determined by the `loop_fn`
      on its first call (and should match `cell.state_size`).
      The outputs are: `finished`, a boolean `Tensor` of
      shape `[batch_size]`, `next_input`: the next input to feed to `cell`,
      `next_cell_state`: the next state to feed to `cell`,
      and `emit_output`: the output to store for this iteration.

      Note that `emit_output` should be a `Tensor` or (possibly nested)
      tuple of tensors with shapes and structure matching `cell.output_size`
      and `cell_output` above.  The parameter `cell_state` and output
      `next_cell_state` may be either a single or (possibly nested) tuple
      of tensors.  The parameter `loop_state` and
      output `next_loop_state` may be either a single or (possibly nested) tuple
      of `Tensor` and `TensorArray` objects.  This last parameter
      may be ignored by `loop_fn` and the return value may be `None`.  If it
      is not `None`, then the `loop_state` will be propagated through the RNN
      loop, for use purely by `loop_fn` to keep track of its own state.
      The `next_loop_state` parameter returned may be `None`.

      The first call to `loop_fn` will be `time = 0`, `cell_output = None`,
      `cell_state = None`, and `loop_state = None`.  For this call:
      The `next_cell_state` value should be the value with which to initialize
      the cell's state.  It may be a final state from a previous RNN or it
      may be the output of `cell.zero_state()`.  It should be a
      (possibly nested) tuple structure of tensors.
      If `cell.state_size` is an integer, this must be
      a `Tensor` of appropriate type and shape `[batch_size, cell.state_size]`.
      If `cell.state_size` is a `TensorShape`, this must be a `Tensor` of
      appropriate type and shape `[batch_size] + cell.state_size`.
      If `cell.state_size` is a (possibly nested) tuple of ints or
      `TensorShape`, this will be a tuple having the corresponding shapes.
      The `emit_output` value may be either `None` or a (possibly nested)
      tuple structure of tensors, e.g.,
      `(tf.zeros(shape_0, dtype=dtype_0), tf.zeros(shape_1, dtype=dtype_1))`.
      If this first `emit_output` return value is `None`,
      then the `emit_ta` result of `raw_rnn` will have the same structure and
      dtypes as `cell.output_size`.  Otherwise `emit_ta` will have the same
      structure, shapes (prepended with a `batch_size` dimension), and dtypes
      as `emit_output`.  The actual values returned for `emit_output` at this
      initializing call are ignored.  Note, this emit structure must be
      consistent across all time steps.

    parallel_iterations: (Default: 32).  The number of iterations to run in
      parallel.  Those operations which do not have any temporal dependency
      and can be run in parallel, will be.  This parameter trades off
      time for space.  Values >> 1 use more memory but take less time,
      while smaller values use less memory but computations take longer.
    swap_memory: Transparently swap the tensors produced in forward inference
      but needed for back prop from GPU to CPU.  This allows training RNNs
      which would typically not fit on a single GPU, with very minimal (or no)
      performance penalty.
    scope: VariableScope for the created subgraph; defaults to "rnn".

  Returns:
    A tuple `(emit_ta, final_state, final_loop_state)` where:

    `emit_ta`: The RNN output `TensorArray`.
       If `loop_fn` returns a (possibly nested) set of Tensors for
       `emit_output` during initialization, (inputs `time = 0`,
       `cell_output = None`, and `loop_state = None`), then `emit_ta` will
       have the same structure, dtypes, and shapes as `emit_output` instead.
       If `loop_fn` returns `emit_output = None` during this call,
       the structure of `cell.output_size` is used:
       If `cell.output_size` is a (possibly nested) tuple of integers
       or `TensorShape` objects, then `emit_ta` will be a tuple having the
       same structure as `cell.output_size`, containing TensorArrays whose
       elements' shapes correspond to the shape data in `cell.output_size`.

    `final_state`: The final cell state.  If `cell.state_size` is an int, this
      will be shaped `[batch_size, cell.state_size]`.  If it is a
      `TensorShape`, this will be shaped `[batch_size] + cell.state_size`.
      If it is a (possibly nested) tuple of ints or `TensorShape`, this will
      be a tuple having the corresponding shapes.

    `final_loop_state`: The final loop state as returned by `loop_fn`.

  Raises:
    TypeError: If `cell` is not an instance of RNNCell, or `loop_fn` is not
      a `callable`.
  """

  _like_rnncell("cell must be an instance of RNNCell", cell)
  if not callable(loop_fn):
    raise TypeError("loop_fn must be a callable")

  parallel_iterations = parallel_iterations or 32

  # Create a new scope in which the caching device is either
  # determined by the parent scope, or is set to place the cached
  # Variable using the same placement as for the rest of the RNN.
  with vs.variable_scope(scope or "rnn") as varscope:
    if varscope.caching_device is None:
      varscope.set_caching_device(lambda op: op.device)

    time = constant_op.constant(0, dtype=dtypes.int32)
    (elements_finished, next_input, initial_state, emit_structure,
     init_loop_state) = loop_fn(
         time, None, None, None)  # time, cell_output, cell_state, loop_state
    flat_input = nest.flatten(next_input)

    # Need a surrogate loop state for the while_loop if none is available.
    loop_state = (init_loop_state if init_loop_state is not None
                  else constant_op.constant(0, dtype=dtypes.int32))

    input_shape = [input_.get_shape() for input_ in flat_input]
    static_batch_size = input_shape[0][0]

    for input_shape_i in input_shape:
      # Static verification that batch sizes all match
      static_batch_size.merge_with(input_shape_i[0])

    batch_size = static_batch_size
    if batch_size is None:
      batch_size = array_ops.shape(flat_input[0])[0]

    nest.assert_same_structure(initial_state, cell.state_size)
    state = initial_state
    flat_state = nest.flatten(state)
    flat_state = [ops.convert_to_tensor(s) for s in flat_state]
    state = nest.pack_sequence_as(structure=state,
                                  flat_sequence=flat_state)

    if emit_structure is not None:
      flat_emit_structure = nest.flatten(emit_structure)
      flat_emit_size = [emit.shape if emit.shape.is_fully_defined() else
                        array_ops.shape(emit) for emit in flat_emit_structure]
      flat_emit_dtypes = [emit.dtype for emit in flat_emit_structure]
    else:
      emit_structure = cell.output_size
      flat_emit_size = nest.flatten(emit_structure)
      flat_emit_dtypes = [flat_state[0].dtype] * len(flat_emit_size)

    flat_emit_ta = [
        tensor_array_ops.TensorArray(
            dtype=dtype_i, dynamic_size=True, size=0, name="rnn_output_%d" % i)
        for i, dtype_i in enumerate(flat_emit_dtypes)]
    emit_ta = nest.pack_sequence_as(structure=emit_structure,
                                    flat_sequence=flat_emit_ta)
    flat_zero_emit = [
        array_ops.zeros(_concat(batch_size, size_i), dtype_i)
        for size_i, dtype_i in zip(flat_emit_size, flat_emit_dtypes)]
    zero_emit = nest.pack_sequence_as(structure=emit_structure,
                                      flat_sequence=flat_zero_emit)

    def condition(unused_time, elements_finished, *_):
      return math_ops.logical_not(math_ops.reduce_all(elements_finished))

    def body(time, elements_finished, current_input,
             emit_ta, state, loop_state):
      """Internal while loop body for raw_rnn.

      Args:
        time: time scalar.
        elements_finished: batch-size vector.
        current_input: possibly nested tuple of input tensors.
        emit_ta: possibly nested tuple of output TensorArrays.
        state: possibly nested tuple of state tensors.
        loop_state: possibly nested tuple of loop state tensors.

      Returns:
        Tuple having the same size as Args but with updated values.
      """
      (next_output, cell_state) = cell(current_input, state)

      nest.assert_same_structure(state, cell_state)
      nest.assert_same_structure(cell.output_size, next_output)

      next_time = time + 1
      (next_finished, next_input, next_state, emit_output,
       next_loop_state) = loop_fn(
           next_time, next_output, cell_state, loop_state)

      nest.assert_same_structure(state, next_state)
      nest.assert_same_structure(current_input, next_input)
      nest.assert_same_structure(emit_ta, emit_output)

      # If loop_fn returns None for next_loop_state, just reuse the
      # previous one.
      loop_state = loop_state if next_loop_state is None else next_loop_state

      def _copy_some_through(current, candidate):
        """Copy some tensors through via array_ops.where."""
        def copy_fn(cur_i, cand_i):
          with ops.colocate_with(cand_i):
            return array_ops.where(elements_finished, cur_i, cand_i)
        return nest.map_structure(copy_fn, current, candidate)

      emit_output = _copy_some_through(zero_emit, emit_output)
      next_state = _copy_some_through(state, next_state)

      emit_ta = nest.map_structure(
          lambda ta, emit: ta.write(time, emit), emit_ta, emit_output)

      elements_finished = math_ops.logical_or(elements_finished, next_finished)

      return (next_time, elements_finished, next_input,
              emit_ta, next_state, loop_state)

    returned = control_flow_ops.while_loop(
        condition, body, loop_vars=[
            time, elements_finished, next_input,
            emit_ta, state, loop_state],
        parallel_iterations=parallel_iterations,
        swap_memory=swap_memory)

    (emit_ta, final_state, final_loop_state) = returned[-3:]

    if init_loop_state is None:
      final_loop_state = None

    return (emit_ta, final_state, final_loop_state)


def static_rnn(cell,
               inputs,
               initial_state=None,
               dtype=None,
               sequence_length=None,
               scope=None):
  """Creates a recurrent neural network specified by RNNCell `cell`.

  The simplest form of RNN network generated is:

  ```python
    state = cell.zero_state(...)
    outputs = []
    for input_ in inputs:
      output, state = cell(input_, state)
      outputs.append(output)
    return (outputs, state)
  ```
  However, a few other options are available:

  An initial state can be provided.
  If the sequence_length vector is provided, dynamic calculation is performed.
  This method of calculation does not compute the RNN steps past the maximum
  sequence length of the minibatch (thus saving computational time),
  and properly propagates the state at an example's sequence length
  to the final state output.

  The dynamic calculation performed is, at time `t` for batch row `b`,

  ```python
    (output, state)(b, t) =
      (t >= sequence_length(b))
        ? (zeros(cell.output_size), states(b, sequence_length(b) - 1))
        : cell(input(b, t), state(b, t - 1))
  ```

  Args:
    cell: An instance of RNNCell.
    inputs: A length T list of inputs, each a `Tensor` of shape
      `[batch_size, input_size]`, or a nested tuple of such elements.
    initial_state: (optional) An initial state for the RNN.
      If `cell.state_size` is an integer, this must be
      a `Tensor` of appropriate type and shape `[batch_size, cell.state_size]`.
      If `cell.state_size` is a tuple, this should be a tuple of
      tensors having shapes `[batch_size, s] for s in cell.state_size`.
    dtype: (optional) The data type for the initial state and expected output.
      Required if initial_state is not provided or RNN state has a heterogeneous
      dtype.
    sequence_length: Specifies the length of each sequence in inputs.
      An int32 or int64 vector (tensor) size `[batch_size]`, values in `[0, T)`.
    scope: VariableScope for the created subgraph; defaults to "rnn".

  Returns:
    A pair (outputs, state) where:

    - outputs is a length T list of outputs (one for each input), or a nested
      tuple of such elements.
    - state is the final state

  Raises:
    TypeError: If `cell` is not an instance of RNNCell.
    ValueError: If `inputs` is `None` or an empty list, or if the input depth
      (column size) cannot be inferred from inputs via shape inference.
  """

  _like_rnncell("cell must be an instance of RNNCell", cell)
  if not nest.is_sequence(inputs):
    raise TypeError("inputs must be a sequence")
  if not inputs:
    raise ValueError("inputs must not be empty")

  outputs = []
  # Create a new scope in which the caching device is either
  # determined by the parent scope, or is set to place the cached
  # Variable using the same placement as for the rest of the RNN.
  with vs.variable_scope(scope or "rnn") as varscope:
    if varscope.caching_device is None:
      varscope.set_caching_device(lambda op: op.device)

    # Obtain the first sequence of the input
    first_input = inputs
    while nest.is_sequence(first_input):
      first_input = first_input[0]

    # Temporarily avoid EmbeddingWrapper and seq2seq badness
    # TODO(lukaszkaiser): remove EmbeddingWrapper
    if first_input.get_shape().ndims != 1:

      input_shape = first_input.get_shape().with_rank_at_least(2)
      fixed_batch_size = input_shape[0]

      flat_inputs = nest.flatten(inputs)
      for flat_input in flat_inputs:
        input_shape = flat_input.get_shape().with_rank_at_least(2)
        batch_size, input_size = input_shape[0], input_shape[1:]
        fixed_batch_size.merge_with(batch_size)
        for i, size in enumerate(input_size):
          if size is None:
            raise ValueError(
                "Input size (dimension %d of inputs) must be accessible via "
                "shape inference, but saw value None." % i)
    else:
      fixed_batch_size = first_input.get_shape().with_rank_at_least(1)[0]

    if fixed_batch_size:
      batch_size = fixed_batch_size
    else:
      batch_size = array_ops.shape(first_input)[0]
    if initial_state is not None:
      state = initial_state
    else:
      if not dtype:
        raise ValueError("If no initial_state is provided, "
                         "dtype must be specified")
      state = cell.zero_state(batch_size, dtype)

    if sequence_length is not None:  # Prepare variables
      sequence_length = ops.convert_to_tensor(
          sequence_length, name="sequence_length")
      if sequence_length.get_shape().ndims not in (None, 1):
        raise ValueError(
            "sequence_length must be a vector of length batch_size")

      def _create_zero_output(output_size):
        # convert int to TensorShape if necessary
        size = _concat(batch_size, output_size)
        output = array_ops.zeros(
            array_ops.stack(size), _infer_state_dtype(dtype, state))
        shape = _concat(fixed_batch_size, output_size, static=True)
        output.set_shape(tensor_shape.TensorShape(shape))
        return output

      output_size = cell.output_size
      flat_output_size = nest.flatten(output_size)
      flat_zero_output = tuple(
          _create_zero_output(size) for size in flat_output_size)
      zero_output = nest.pack_sequence_as(
          structure=output_size, flat_sequence=flat_zero_output)

      sequence_length = math_ops.to_int32(sequence_length)
      min_sequence_length = math_ops.reduce_min(sequence_length)
      max_sequence_length = math_ops.reduce_max(sequence_length)

    for time, input_ in enumerate(inputs):
      if time > 0:
        varscope.reuse_variables()
      # pylint: disable=cell-var-from-loop
      call_cell = lambda: cell(input_, state)
      # pylint: enable=cell-var-from-loop
      if sequence_length is not None:
        (output, state) = _rnn_step(
            time=time,
            sequence_length=sequence_length,
            min_sequence_length=min_sequence_length,
            max_sequence_length=max_sequence_length,
            zero_output=zero_output,
            state=state,
            call_cell=call_cell,
            state_size=cell.state_size)
      else:
        (output, state) = call_cell()

      outputs.append(output)

    return (outputs, state)


def static_state_saving_rnn(cell,
                            inputs,
                            state_saver,
                            state_name,
                            sequence_length=None,
                            scope=None):
  """RNN that accepts a state saver for time-truncated RNN calculation.

  Args:
    cell: An instance of `RNNCell`.
    inputs: A length T list of inputs, each a `Tensor` of shape
      `[batch_size, input_size]`.
    state_saver: A state saver object with methods `state` and `save_state`.
    state_name: Python string or tuple of strings.  The name to use with the
      state_saver. If the cell returns tuples of states (i.e.,
      `cell.state_size` is a tuple) then `state_name` should be a tuple of
      strings having the same length as `cell.state_size`.  Otherwise it should
      be a single string.
    sequence_length: (optional) An int32/int64 vector size [batch_size].
      See the documentation for rnn() for more details about sequence_length.
    scope: VariableScope for the created subgraph; defaults to "rnn".

  Returns:
    A pair (outputs, state) where:
      outputs is a length T list of outputs (one for each input)
      states is the final state

  Raises:
    TypeError: If `cell` is not an instance of RNNCell.
    ValueError: If `inputs` is `None` or an empty list, or if the arity and
     type of `state_name` does not match that of `cell.state_size`.
  """
  state_size = cell.state_size
  state_is_tuple = nest.is_sequence(state_size)
  state_name_tuple = nest.is_sequence(state_name)

  if state_is_tuple != state_name_tuple:
    raise ValueError("state_name should be the same type as cell.state_size.  "
                     "state_name: %s, cell.state_size: %s" % (str(state_name),
                                                              str(state_size)))

  if state_is_tuple:
    state_name_flat = nest.flatten(state_name)
    state_size_flat = nest.flatten(state_size)

    if len(state_name_flat) != len(state_size_flat):
      raise ValueError("#elems(state_name) != #elems(state_size): %d vs. %d" %
                       (len(state_name_flat), len(state_size_flat)))

    initial_state = nest.pack_sequence_as(
        structure=state_size,
        flat_sequence=[state_saver.state(s) for s in state_name_flat])
  else:
    initial_state = state_saver.state(state_name)

  (outputs, state) = static_rnn(
      cell,
      inputs,
      initial_state=initial_state,
      sequence_length=sequence_length,
      scope=scope)

  if state_is_tuple:
    flat_state = nest.flatten(state)
    state_name = nest.flatten(state_name)
    save_state = [
        state_saver.save_state(name, substate)
        for name, substate in zip(state_name, flat_state)
    ]
  else:
    save_state = [state_saver.save_state(state_name, state)]

  with ops.control_dependencies(save_state):
    last_output = outputs[-1]
    flat_last_output = nest.flatten(last_output)
    flat_last_output = [
        array_ops.identity(output) for output in flat_last_output
    ]
    outputs[-1] = nest.pack_sequence_as(
        structure=last_output, flat_sequence=flat_last_output)

  return (outputs, state)


def static_bidirectional_rnn(cell_fw,
                             cell_bw,
                             inputs,
                             initial_state_fw=None,
                             initial_state_bw=None,
                             dtype=None,
                             sequence_length=None,
                             scope=None):
  """Creates a bidirectional recurrent neural network.

  Similar to the unidirectional case above (rnn) but takes input and builds
  independent forward and backward RNNs with the final forward and backward
  outputs depth-concatenated, such that the output will have the format
  [time][batch][cell_fw.output_size + cell_bw.output_size]. The input_size of
  forward and backward cell must match. The initial state for both directions
  is zero by default (but can be set optionally) and no intermediate states are
  ever returned -- the network is fully unrolled for the given (passed in)
  length(s) of the sequence(s) or completely unrolled if length(s) is not given.

  Args:
    cell_fw: An instance of RNNCell, to be used for forward direction.
    cell_bw: An instance of RNNCell, to be used for backward direction.
    inputs: A length T list of inputs, each a tensor of shape
      [batch_size, input_size], or a nested tuple of such elements.
    initial_state_fw: (optional) An initial state for the forward RNN.
      This must be a tensor of appropriate type and shape
      `[batch_size, cell_fw.state_size]`.
      If `cell_fw.state_size` is a tuple, this should be a tuple of
      tensors having shapes `[batch_size, s] for s in cell_fw.state_size`.
    initial_state_bw: (optional) Same as for `initial_state_fw`, but using
      the corresponding properties of `cell_bw`.
    dtype: (optional) The data type for the initial state.  Required if
      either of the initial states are not provided.
    sequence_length: (optional) An int32/int64 vector, size `[batch_size]`,
      containing the actual lengths for each of the sequences.
    scope: VariableScope for the created subgraph; defaults to
      "bidirectional_rnn"

  Returns:
    A tuple (outputs, output_state_fw, output_state_bw) where:
      outputs is a length `T` list of outputs (one for each input), which
        are depth-concatenated forward and backward outputs.
      output_state_fw is the final state of the forward rnn.
      output_state_bw is the final state of the backward rnn.

  Raises:
    TypeError: If `cell_fw` or `cell_bw` is not an instance of `RNNCell`.
    ValueError: If inputs is None or an empty list.
  """

  _like_rnncell("cell_fw must be an instance of RNNCell", cell_fw)
  _like_rnncell("cell_bw must be an instance of RNNCell", cell_bw)
  if not nest.is_sequence(inputs):
    raise TypeError("inputs must be a sequence")
  if not inputs:
    raise ValueError("inputs must not be empty")

  with vs.variable_scope(scope or "bidirectional_rnn"):
    # Forward direction
    with vs.variable_scope("fw") as fw_scope:
      output_fw, output_state_fw = static_rnn(
          cell_fw,
          inputs,
          initial_state_fw,
          dtype,
          sequence_length,
          scope=fw_scope)

    # Backward direction
    with vs.variable_scope("bw") as bw_scope:
      reversed_inputs = _reverse_seq(inputs, sequence_length)
      tmp, output_state_bw = static_rnn(
          cell_bw,
          reversed_inputs,
          initial_state_bw,
          dtype,
          sequence_length,
          scope=bw_scope)

  output_bw = _reverse_seq(tmp, sequence_length)
  # Concat each of the forward/backward outputs
  flat_output_fw = nest.flatten(output_fw)
  flat_output_bw = nest.flatten(output_bw)

  flat_outputs = tuple(
      array_ops.concat([fw, bw], 1)
      for fw, bw in zip(flat_output_fw, flat_output_bw))

  outputs = nest.pack_sequence_as(
      structure=output_fw, flat_sequence=flat_outputs)

  return (outputs, output_state_fw, output_state_bw)