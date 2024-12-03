import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Simulated DataFrames for each time of day
data_morning = {
    'Weight': [82.5, 78.3, 74.1, 65.3, 83.0, 77.5, 66.3, 56.1, 60.9, 53.1],
    'Height': [175, 178, 172, 167, 183, 172, 167, 162, 165, 160]
}
data_afternoon = {
    'Weight': [97.7, 73.7, 83.0, 66.3, 60.9, 53.1, 56.1, 73.1, 77.4, 63.4],
    'Height': [176.6, 175, 181, 167, 162, 165, 162, 172, 172, 160]
}
data_night = {
    'Weight': [82.6, 71.9, 73.1, 55.3, 78.2, 76.7, 50.5, 60.9, 65.3, 82.6],
    'Height': [175, 176, 172, 162, 181, 167, 160, 165, 167, 175]
}

# Convert to DataFrames
df_morning = pd.DataFrame(data_morning)
df_afternoon = pd.DataFrame(data_afternoon)
df_night = pd.DataFrame(data_night)

# Calculate averages
avg_weight = [df_morning['Weight'].mean(), df_afternoon['Weight'].mean(), df_night['Weight'].mean()]
avg_height = [df_morning['Height'].mean(), df_afternoon['Height'].mean(), df_night['Height'].mean()]

# Plot
times = ['Morning', 'Afternoon', 'Night']
x = np.arange(len(times))

fig, ax = plt.subplots(figsize=(8, 5))
bar_width = 0.35

# Bars for weight and height
ax.bar(x - bar_width/2, avg_weight, width=bar_width, label='Average Weight (kg)')
ax.bar(x + bar_width/2, avg_height, width=bar_width, label='Average Height (cm)')

# Add labels
ax.set_xlabel('Time of Day')
ax.set_ylabel('Measurement')
ax.set_title('Average Weight and Height Across Different Times of Day')
ax.set_xticks(x)
ax.set_xticklabels(times)
ax.legend()

# Show plot
plt.show()
